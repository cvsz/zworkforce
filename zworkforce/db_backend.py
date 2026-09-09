from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager
import re
from typing import Any, Iterator, Sequence


def is_postgres_target(target: str) -> bool:
    value = str(target).lower()
    return value.startswith("postgresql://") or value.startswith("postgres://")


def rewrite_qmark(sql: str) -> str:
    out: list[str] = []
    single = double = False
    i = 0
    while i < len(sql):
        ch = sql[i]
        if ch == "'" and not double:
            out.append(ch)
            if single and i + 1 < len(sql) and sql[i + 1] == "'":
                out.append("'")
                i += 2
                continue
            single = not single
        elif ch == '"' and not single:
            out.append(ch)
            double = not double
        elif ch == "?" and not single and not double:
            out.append("%s")
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def postgres_sql(sql: str) -> str:
    stripped = sql.strip()
    upper = stripped.upper()
    if upper.startswith("PRAGMA "):
        return ""
    if upper == "BEGIN IMMEDIATE":
        return "BEGIN"
    changed = re.sub(r"\bINSERT\s+OR\s+IGNORE\s+INTO\b", "INSERT INTO", sql, flags=re.I)
    if changed != sql and " ON CONFLICT " not in changed.upper():
        suffix = ";" if changed.rstrip().endswith(";") else ""
        base = changed.rstrip().removesuffix(";").rstrip()
        changed = base + " ON CONFLICT DO NOTHING" + suffix
    return rewrite_qmark(changed)


def postgres_schema(script: str) -> str:
    script = re.sub(r"\bid\s+INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b", "id BIGSERIAL PRIMARY KEY", script, flags=re.I)
    script = re.sub(r"\bAUTOINCREMENT\b", "", script, flags=re.I)
    return script


def secure_postgres_dsn(dsn: str) -> str:
    if "sslmode=" in dsn:
        return dsn
    local_prefixes = (
        "postgresql://localhost",
        "postgres://localhost",
        "postgresql://127.0.0.1",
        "postgres://127.0.0.1",
    )
    sslmode = "prefer" if dsn.startswith(local_prefixes) else "require"
    separator = "&" if "?" in dsn else "?"
    return f"{dsn}{separator}sslmode={sslmode}"


class CompatRow(Mapping[str, Any]):
    def __init__(self, names: Sequence[str], values: Sequence[Any]):
        self._names = tuple(names)
        self._values = tuple(values)
        self._map = dict(zip(self._names, self._values))

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return self._map[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._names)

    def __len__(self) -> int:
        return len(self._names)

    def keys(self):
        return self._names


class EmptyResult:
    rowcount = 0

    def fetchone(self):
        return None

    def fetchall(self):
        return []


class PostgresResult:
    def __init__(self, cursor):
        self.cursor = cursor
        self.rowcount = cursor.rowcount
        self._names = tuple(col.name for col in cursor.description) if cursor.description else ()

    def _row(self, raw):
        return CompatRow(self._names, raw) if raw is not None and self._names else raw

    def fetchone(self):
        return self._row(self.cursor.fetchone())

    def fetchall(self):
        return [self._row(row) for row in self.cursor.fetchall()]


class PostgresConnection:
    def __init__(self, connection):
        self._connection = connection

    def execute(self, sql: str, params: Sequence[Any] | None = None):
        translated = postgres_sql(sql)
        if not translated:
            return EmptyResult()
        cursor = self._connection.execute(translated, tuple(params or ()))
        return PostgresResult(cursor)

    def executescript(self, script: str):
        for statement in postgres_schema(script).split(";"):
            if statement.strip():
                self.execute(statement)
        return EmptyResult()

    def close(self):
        self._connection.close()


class PostgresPool:
    def __init__(self, dsn: str, min_size: int = 1, max_size: int = 10):
        from psycopg.rows import tuple_row
        from psycopg_pool import ConnectionPool

        self._dsn = secure_postgres_dsn(dsn)
        self._min_size = max(1, min_size)
        self._max_size = max(self._min_size, max_size)
        self._pool = ConnectionPool(
            self._dsn,
            min_size=self._min_size,
            max_size=self._max_size,
            kwargs={"autocommit": True, "row_factory": tuple_row},
        )

    @contextmanager
    def connection(self):
        with self._pool.connection() as conn:
            yield PostgresConnection(conn)

    def close(self):
        self._pool.close()


_postgres_pools: dict[str, PostgresPool] = {}


def get_postgres_pool(dsn: str, min_size: int = 1, max_size: int = 10) -> PostgresPool:
    key = secure_postgres_dsn(dsn)
    if key not in _postgres_pools:
        _postgres_pools[key] = PostgresPool(key, min_size=min_size, max_size=max_size)
    return _postgres_pools[key]


def connect_postgres(dsn: str):
    try:
        import psycopg
        from psycopg.rows import tuple_row
    except ImportError as exc:
        raise RuntimeError("PostgreSQL backend requires psycopg; install zworkforce[postgres]") from exc
    connection = psycopg.connect(secure_postgres_dsn(dsn), autocommit=True, row_factory=tuple_row)
    return PostgresConnection(connection)
