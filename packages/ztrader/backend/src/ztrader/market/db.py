from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import lru_cache
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Engine,
    Float,
    Integer,
    String,
    create_engine,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from zkbtrader.audit import AuditEvent
from zkbtrader.config import get_settings
from zkbtrader.models import IntentSide, PaperOrder


class Base(DeclarativeBase):
    pass


class AuditEventRecord(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    message: Mapped[str] = mapped_column(String(512), nullable=False)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    actor: Mapped[str] = mapped_column(String(64), nullable=False, default="system")
    metadata_json: Mapped[dict[str, str | int | float | bool]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PaperOrderRecord(Base):
    __tablename__ = "paper_orders"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    side: Mapped[str] = mapped_column(String(32), nullable=False)
    notional: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    base_amount: Mapped[float] = mapped_column(Float, nullable=False)
    fee: Mapped[float] = mapped_column(Float, nullable=False)
    strategy_id: Mapped[str] = mapped_column(String(128), nullable=False)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    simulated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class BacktestRunRecord(Base):
    __tablename__ = "backtest_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    strategy_id: Mapped[str] = mapped_column(String(128), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    candles_seen: Mapped[int] = mapped_column(Integer, nullable=False)
    orders_created: Mapped[int] = mapped_column(Integer, nullable=False)
    ending_usdt: Mapped[float] = mapped_column(Float, nullable=False)
    ending_btc: Mapped[float] = mapped_column(Float, nullable=False)
    metadata_json: Mapped[dict[str, str | int | float | bool]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


BacktestMetadataValue = str | int | float | bool


@dataclass(frozen=True)
class BacktestRun:
    strategy_id: str
    symbol: str
    candles_seen: int
    orders_created: int
    ending_usdt: float
    ending_btc: float
    metadata_json: dict[str, BacktestMetadataValue] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(settings.database_url, future=True)


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(
        bind=get_engine(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class AuditEventRepository:
    def add(self, event: AuditEvent) -> AuditEvent:
        with session_scope() as session:
            session.add(
                AuditEventRecord(
                    id=event.id,
                    event_type=event.event_type,
                    message=event.message,
                    request_id=event.request_id,
                    actor=event.actor,
                    metadata_json=event.metadata,
                    created_at=event.created_at,
                )
            )
        return event

    def list_events(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        event_type: str | None = None,
        request_id: str | None = None,
        actor: str | None = None,
    ) -> list[AuditEvent]:
        with session_scope() as session:
            statement = select(AuditEventRecord)
            if event_type is not None:
                statement = statement.where(AuditEventRecord.event_type == event_type)
            if request_id is not None:
                statement = statement.where(AuditEventRecord.request_id == request_id)
            if actor is not None:
                statement = statement.where(AuditEventRecord.actor == actor)

            rows = session.execute(
                statement
                .order_by(AuditEventRecord.created_at.desc())
                .offset(offset)
                .limit(limit)
            ).scalars()
            records = list(rows)
        records.reverse()
        return [
            AuditEvent(
                id=row.id,
                event_type=row.event_type,
                message=row.message,
                request_id=row.request_id,
                actor=row.actor,
                metadata=row.metadata_json,
                created_at=_ensure_utc(row.created_at),
            )
            for row in records
        ]


class PaperOrderRepository:
    def add(self, order: PaperOrder) -> PaperOrder:
        with session_scope() as session:
            session.add(
                PaperOrderRecord(
                    id=order.id,
                    symbol=order.symbol,
                    side=order.side.value,
                    notional=order.notional,
                    price=order.price,
                    base_amount=order.base_amount,
                    fee=order.fee,
                    strategy_id=order.strategy_id,
                    request_id=order.request_id,
                    simulated=True,
                    created_at=order.created_at,
                )
            )
        return order

    def list_orders(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        symbol: str | None = None,
        strategy_id: str | None = None,
        side: str | None = None,
    ) -> list[PaperOrder]:
        with session_scope() as session:
            statement = select(PaperOrderRecord)
            if symbol is not None:
                statement = statement.where(PaperOrderRecord.symbol == symbol)
            if strategy_id is not None:
                statement = statement.where(PaperOrderRecord.strategy_id == strategy_id)
            if side is not None:
                statement = statement.where(PaperOrderRecord.side == side)

            rows = session.execute(
                statement
                .order_by(PaperOrderRecord.created_at.desc())
                .offset(offset)
                .limit(limit)
            ).scalars()
            records = list(rows)
        records.reverse()
        return [
            PaperOrder(
                id=row.id,
                symbol=row.symbol,
                side=IntentSide(row.side),
                notional=row.notional,
                price=row.price,
                base_amount=row.base_amount,
                fee=row.fee,
                strategy_id=row.strategy_id,
                request_id=row.request_id,
                created_at=_ensure_utc(row.created_at),
            )
            for row in records
        ]


class BacktestRunRepository:
    def add(self, run: BacktestRun) -> BacktestRun:
        with session_scope() as session:
            session.add(
                BacktestRunRecord(
                    id=run.id,
                    strategy_id=run.strategy_id,
                    symbol=run.symbol,
                    candles_seen=run.candles_seen,
                    orders_created=run.orders_created,
                    ending_usdt=run.ending_usdt,
                    ending_btc=run.ending_btc,
                    metadata_json=run.metadata_json,
                    created_at=run.created_at,
                )
            )
        return run

    def list_runs(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        symbol: str | None = None,
        strategy_id: str | None = None,
    ) -> list[BacktestRun]:
        with session_scope() as session:
            statement = select(BacktestRunRecord)
            if symbol is not None:
                statement = statement.where(BacktestRunRecord.symbol == symbol)
            if strategy_id is not None:
                statement = statement.where(BacktestRunRecord.strategy_id == strategy_id)

            rows = session.execute(
                statement
                .order_by(BacktestRunRecord.created_at.desc())
                .offset(offset)
                .limit(limit)
            ).scalars()
            records = list(rows)
        records.reverse()
        return [self._to_domain(row) for row in records]

    def get_run(self, run_id: str) -> BacktestRun | None:
        with session_scope() as session:
            row = session.get(BacktestRunRecord, run_id)
        if row is None:
            return None
        return self._to_domain(row)

    def _to_domain(self, row: BacktestRunRecord) -> BacktestRun:
        return BacktestRun(
            id=row.id,
            strategy_id=row.strategy_id,
            symbol=row.symbol,
            candles_seen=row.candles_seen,
            orders_created=row.orders_created,
            ending_usdt=row.ending_usdt,
            ending_btc=row.ending_btc,
            metadata_json=row.metadata_json,
            created_at=_ensure_utc(row.created_at),
        )
