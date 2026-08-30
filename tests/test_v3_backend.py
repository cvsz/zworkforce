from types import SimpleNamespace
import unittest

from zworkforce.db_backend import CompatRow, PostgresConnection, postgres_schema, postgres_sql


class BackendTests(unittest.TestCase):
    def test_qmark_and_transactions(self):
        self.assertEqual(postgres_sql("BEGIN IMMEDIATE"), "BEGIN")
        self.assertEqual(postgres_sql("SELECT * FROM x WHERE a=? AND b='?'"), "SELECT * FROM x WHERE a=%s AND b='?'")

    def test_insert_or_ignore(self):
        sql = postgres_sql("INSERT OR IGNORE INTO x(a) VALUES(?)")
        self.assertIn("INSERT INTO x", sql)
        self.assertIn("ON CONFLICT DO NOTHING", sql)

    def test_schema_autoincrement(self):
        self.assertIn("BIGSERIAL PRIMARY KEY", postgres_schema("id INTEGER PRIMARY KEY AUTOINCREMENT"))

    def test_compat_row(self):
        row = CompatRow(("a","b"), (1,2))
        self.assertEqual(row[0], 1)
        self.assertEqual(row["b"], 2)
        self.assertEqual(dict(row), {"a":1,"b":2})

    def test_postgres_connection_executes_translated_schema_statements(self):
        class RecordingConnection:
            def __init__(self):
                self.statements = []

            def execute(self, sql, params=()):
                self.statements.append((sql, params))

        connection = RecordingConnection()
        PostgresConnection(connection).executescript(
            "CREATE TABLE x(id INTEGER PRIMARY KEY AUTOINCREMENT);"
            "CREATE INDEX ix ON x(id);"
        )
        self.assertEqual(len(connection.statements), 2)
        self.assertIn("BIGSERIAL PRIMARY KEY", connection.statements[0][0])

    def test_postgres_connection_translates_runtime_sql(self):
        class RecordingConnection:
            def __init__(self):
                self.statements = []

            def execute(self, sql, params=()):
                self.statements.append((sql, params))

        connection = RecordingConnection()
        PostgresConnection(connection).execute("INSERT OR IGNORE INTO x(a) VALUES(?)", (1,))
        PostgresConnection(connection).execute("BEGIN IMMEDIATE")
        self.assertEqual(connection.statements[0], ("INSERT INTO x(a) VALUES(%s) ON CONFLICT DO NOTHING", (1,)))
        self.assertEqual(connection.statements[1], ("BEGIN", ()))

    def test_postgres_connection_preserves_named_result_access(self):
        class Result:
            description = (SimpleNamespace(name="id"),)
            rowcount = 1

            def fetchone(self):
                return (7,)

            def fetchall(self):
                return [(7,)]

        class RecordingConnection:
            def execute(self, sql, params=()):
                return Result()

        result = PostgresConnection(RecordingConnection()).execute("SELECT id FROM x")
        self.assertEqual(result.fetchone()["id"], 7)


if __name__ == "__main__":
    unittest.main()
