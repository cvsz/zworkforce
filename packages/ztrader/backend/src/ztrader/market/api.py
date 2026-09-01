from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from html import escape
from typing import NoReturn

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from zkbtrader import __version__
from zkbtrader.adapters.kucoin import (
    InvalidMarketDataResponse,
    KucoinReadOnlyAdapter,
    MarketDataError,
    MarketDataUnavailable,
)
from zkbtrader.audit import AuditEvent
from zkbtrader.backtest import BacktestEngine
from zkbtrader.config import get_settings
from zkbtrader.db import (
    AuditEventRepository,
    BacktestRun,
    BacktestRunRepository,
    Base,
    PaperOrderRepository,
    get_engine,
)
from zkbtrader.models import IntentSide, PaperPortfolio, StrategyIntent
from zkbtrader.paper import PaperExecutionEngine
from zkbtrader.risk import RiskEngine
from zkbtrader.strategy import Candle, MovingAverageCrossoverStrategy

AuditValue = str | int | float | bool | dict[str, str | int | float | bool]
BacktestValue = str | int | float | bool | dict[str, str | int | float | bool]


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    Base.metadata.create_all(bind=get_engine())
    yield


app = FastAPI(title="ZKBTrader", version=__version__, lifespan=lifespan)
audit_repo = AuditEventRepository()
order_repo = PaperOrderRepository()
backtest_repo = BacktestRunRepository()
paper_engine = PaperExecutionEngine(PaperPortfolio())


class BacktestCandleIn(BaseModel):
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float


class BacktestRunIn(BaseModel):
    symbol: str = "BTC/USDT"
    fast: int = Field(default=3, gt=0)
    slow: int = Field(default=5, gt=0)
    notional: float = Field(default=25.0, gt=0)
    starting_usdt: float = Field(default=1000.0, ge=0)
    starting_btc: float = Field(default=0.0, ge=0)
    candles: list[BacktestCandleIn]


def _market_adapter() -> KucoinReadOnlyAdapter:
    settings = get_settings()
    timeout_seconds = getattr(settings, "exchange_timeout_seconds", 5.0)
    return KucoinReadOnlyAdapter(
        base_url=settings.exchange_base_url,
        sandbox=settings.exchange_sandbox,
        timeout=timeout_seconds,
    )


def _normalize_market_symbol(symbol: str) -> str:
    return symbol.replace("-", "/").upper()


def _raise_market_error(exc: MarketDataError) -> NoReturn:
    if isinstance(exc, InvalidMarketDataResponse):
        raise HTTPException(
            status_code=502,
            detail="market data upstream returned an invalid response",
        ) from exc
    if isinstance(exc, MarketDataUnavailable):
        raise HTTPException(status_code=503, detail="market data service unavailable") from exc
    raise HTTPException(status_code=502, detail="market data request failed") from exc


def _serialize_backtest_run(run: BacktestRun) -> dict[str, BacktestValue]:
    return {
        "run_id": run.id,
        "strategy_id": run.strategy_id,
        "symbol": run.symbol,
        "candles_seen": run.candles_seen,
        "orders_created": run.orders_created,
        "ending_usdt": run.ending_usdt,
        "ending_btc": run.ending_btc,
        "created_at": run.created_at.isoformat(),
        "metadata": run.metadata_json,
    }


def _clean_filter(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned if cleaned else None


def _bool_text(value: bool) -> str:
    return "true" if value else "false"


def _html_link(path: str, *, label: str | None = None) -> str:
    return f'<a href="{escape(path)}">{escape(label or path)}</a>'


def _render_links(links: list[tuple[str, str]]) -> str:
    return "".join(f"<li>{_html_link(path, label=label)}</li>" for path, label in links)


def _render_order_rows() -> str:
    try:
        orders = order_repo.list_orders(limit=5)
    except Exception:
        return '<p class="muted">latest paper orders unavailable</p>'

    if not orders:
        return '<p class="muted">no paper orders yet</p>'

    rows = "".join(
        "<tr>"
        f"<td>{escape(order.created_at.isoformat())}</td>"
        f"<td>{escape(order.symbol)}</td>"
        f"<td>{escape(order.side.value)}</td>"
        f"<td>{order.notional:.2f}</td>"
        f"<td>{order.price:.2f}</td>"
        f"<td>{escape(order.strategy_id)}</td>"
        "</tr>"
        for order in orders
    )
    return (
        "<table><thead><tr>"
        "<th>created_at</th><th>symbol</th><th>side</th><th>notional</th>"
        "<th>price</th><th>strategy_id</th>"
        f"</tr></thead><tbody>{rows}</tbody></table>"
    )


def _render_audit_rows() -> str:
    try:
        events = audit_repo.list_events(limit=5)
    except Exception:
        return '<p class="muted">latest audit events unavailable</p>'

    if not events:
        return '<p class="muted">no audit events yet</p>'

    rows = "".join(
        "<tr>"
        f"<td>{escape(event.event_type)}</td>"
        f"<td>{escape(event.message)}</td>"
        f"<td>{escape(event.request_id)}</td>"
        f"<td>{escape(event.created_at.isoformat())}</td>"
        "</tr>"
        for event in events
    )
    return (
        "<table><thead><tr>"
        "<th>event_type</th><th>message</th><th>request_id</th><th>created_at</th>"
        f"</tr></thead><tbody>{rows}</tbody></table>"
    )


def _render_backtest_rows() -> str:
    try:
        runs = backtest_repo.list_runs(limit=5)
    except Exception:
        return '<p class="muted">latest backtest runs unavailable</p>'

    if not runs:
        return '<p class="muted">no backtest runs yet</p>'

    rows = "".join(
        "<tr>"
        f"<td>{escape(run.created_at.isoformat())}</td>"
        f"<td>{escape(run.id)}</td>"
        f"<td>{escape(run.symbol)}</td>"
        f"<td>{run.candles_seen}</td>"
        f"<td>{run.orders_created}</td>"
        f"<td>{run.ending_usdt:.2f}</td>"
        f"<td>{run.ending_btc:.8f}</td>"
        "</tr>"
        for run in runs
    )
    return (
        "<table><thead><tr>"
        "<th>created_at</th><th>run_id</th><th>symbol</th><th>candles_seen</th>"
        "<th>orders_created</th><th>ending_usdt</th><th>ending_btc</th>"
        f"</tr></thead><tbody>{rows}</tbody></table>"
    )


def _paginated_response(items: Sequence[object], *, limit: int, offset: int) -> dict[str, object]:
    return {
        "items": items,
        "limit": limit,
        "offset": offset,
        "count": len(items),
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/ready")
def ready() -> dict[str, str]:
    settings = get_settings()
    return {"status": "ready", "execution_mode": settings.execution_mode.value}


@app.get("/version")
def version() -> dict[str, str]:
    return {"version": __version__}


@app.get("/metrics")
def metrics() -> str:
    return 'zkbtrader_info{mode="paper"} 1\n'


@app.head("/")
def dashboard_head() -> Response:
    return Response(status_code=200)


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    settings = get_settings()
    safe = settings.execution_mode.value == "paper" and settings.live_trading_enabled is False
    risk = RiskEngine(kill_switch=settings.global_kill_switch)
    kill_switch_status = "enabled" if risk.kill_switch else "disabled"
    risk_status = "blocked" if risk.kill_switch else "active"

    market_links = [
        ("/api/v1/markets", "/api/v1/markets"),
        ("/api/v1/markets/BTC-USDT/ticker", "/api/v1/markets/BTC-USDT/ticker"),
        ("/api/v1/markets/BTC-USDT/candles", "/api/v1/markets/BTC-USDT/candles"),
        ("/api/v1/markets/BTC-USDT/orderbook", "/api/v1/markets/BTC-USDT/orderbook"),
        ("/api/v1/markets/server-time", "/api/v1/markets/server-time"),
    ]
    quick_links = [
        ("/api/v1/config/safe", "/api/v1/config/safe"),
        ("/api/v1/risk/status", "/api/v1/risk/status"),
        ("/api/v1/paper/orders", "/api/v1/paper/orders"),
        ("/api/v1/audit/events", "/api/v1/audit/events"),
        ("/api/v1/backtests", "/api/v1/backtests"),
    ]

    return f"""
<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <title>ZKBTrader Dashboard v2</title>
  <style>
    :root {{
      color-scheme: light;
      font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif;
    }}
    body {{ margin: 0; background: #f5f7fb; color: #1f2937; }}
    main {{ max-width: 1080px; margin: 0 auto; padding: 24px; }}
    h1 {{ margin: 0 0 8px; }}
    h2 {{ margin: 0 0 12px; font-size: 1.1rem; }}
    p {{ margin: 8px 0; }}
    ul {{ margin: 0; padding-left: 20px; }}
    .banner {{
      background: #111827;
      color: #f9fafb;
      border-bottom: 4px solid #ef4444;
      padding: 16px 24px;
      font-weight: 700;
      letter-spacing: 0.03em;
    }}
    .grid {{
      display: grid;
      gap: 16px;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      margin-top: 16px;
    }}
    .card {{
      background: #ffffff;
      border: 1px solid #dbe3ee;
      border-radius: 10px;
      padding: 16px;
    }}
    .muted {{ color: #6b7280; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.92rem; }}
    th, td {{ border-bottom: 1px solid #e5e7eb; text-align: left; padding: 8px 6px; }}
    th {{ background: #f9fafb; font-weight: 600; }}
    a {{ color: #0f4c81; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <div class="banner">PAPER MODE | LIVE TRADING DISABLED</div>
  <main>
    <h1>ZKBTrader</h1>
    <p class="muted">Operational dashboard for paper-trading safety and observability.</p>

    <div class="grid">
      <section class="card">
        <h2>System</h2>
        <ul>
          <li>version: <code>{escape(__version__)}</code></li>
          <li>Execution Mode: <strong>{escape(settings.execution_mode.value)}</strong></li>
          <li>{_html_link("/health", label="health endpoint")}</li>
          <li>{_html_link("/ready", label="readiness endpoint")}</li>
        </ul>
      </section>

      <section class="card">
        <h2>Safety</h2>
        <ul>
          <li>safe: <strong>{_bool_text(safe)}</strong></li>
          <li>
            live_trading_enabled: <strong>{_bool_text(settings.live_trading_enabled)}</strong>
          </li>
          <li>kill switch: <strong>{kill_switch_status}</strong> ({escape(risk_status)})</li>
          <li>{_html_link("/api/v1/safety/live-trading-disabled")}</li>
        </ul>
      </section>

      <section class="card">
        <h2>Market Data</h2>
        <ul>{_render_links(market_links)}</ul>
      </section>

      <section class="card">
        <h2>API Quick Links</h2>
        <ul>{_render_links(quick_links)}</ul>
      </section>
    </div>

    <div class="grid">
      <section class="card">
        <h2>Paper Orders</h2>
        {_render_order_rows()}
      </section>

      <section class="card">
        <h2>Audit Events</h2>
        {_render_audit_rows()}
      </section>
    </div>

    <div class="grid">
      <section class="card">
        <h2>Backtests</h2>
        <p>{_html_link("/api/v1/backtests", label="view all backtest runs")}</p>
        {_render_backtest_rows()}
      </section>
    </div>
  </main>
</body>
</html>
"""


@app.get("/api/v1/config/safe")
def safe_config() -> dict[str, str | float | bool]:
    return get_settings().redacted()


@app.get("/api/v1/markets")
def markets() -> dict[str, list[str]]:
    adapter = _market_adapter()
    try:
        symbols = adapter.list_symbols()
    except MarketDataError as exc:
        _raise_market_error(exc)
    return {"symbols": [entry.symbol for entry in symbols]}


@app.get("/api/v1/markets/server-time")
def server_time() -> dict[str, str | int]:
    adapter = _market_adapter()
    try:
        result = adapter.get_server_time()
    except MarketDataError as exc:
        _raise_market_error(exc)
    return {"epoch_ms": result.epoch_ms, "iso_time": result.iso_time}


@app.get("/api/v1/markets/{symbol}/ticker")
def ticker(symbol: str) -> dict[str, str | float]:
    adapter = _market_adapter()
    try:
        result = adapter.get_ticker(_normalize_market_symbol(symbol))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid market request parameter") from exc
    except MarketDataError as exc:
        _raise_market_error(exc)
    return {"symbol": result.symbol, "price": result.price}


@app.get("/api/v1/markets/{symbol}/candles")
def candles(symbol: str, timeframe: str = "1hour", limit: int = 100) -> dict[str, object]:
    adapter = _market_adapter()
    if limit <= 0 or limit > 1500:
        raise HTTPException(status_code=400, detail="invalid market request parameter")

    try:
        series = adapter.get_candles(
            _normalize_market_symbol(symbol), timeframe=timeframe, limit=limit
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid market request parameter") from exc
    except MarketDataError as exc:
        _raise_market_error(exc)

    return {
        "symbol": _normalize_market_symbol(symbol),
        "timeframe": timeframe,
        "candles": [
            {
                "timestamp": candle.timestamp,
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume,
                "turnover": candle.turnover,
            }
            for candle in series
        ],
    }


@app.get("/api/v1/markets/{symbol}/orderbook")
def orderbook(symbol: str, depth: int = 20) -> dict[str, object]:
    adapter = _market_adapter()
    if depth <= 0 or depth > 100:
        raise HTTPException(status_code=400, detail="invalid market request parameter")

    try:
        snapshot = adapter.get_orderbook(_normalize_market_symbol(symbol), depth=depth)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid market request parameter") from exc
    except MarketDataError as exc:
        _raise_market_error(exc)

    return {
        "symbol": snapshot.symbol,
        "depth": snapshot.depth,
        "sequence": snapshot.sequence,
        "bids": [{"price": level.price, "size": level.size} for level in snapshot.bids],
        "asks": [{"price": level.price, "size": level.size} for level in snapshot.asks],
    }


@app.get("/api/v1/paper/orders")
def paper_orders(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    symbol: str | None = None,
    strategy_id: str | None = None,
    side: str | None = None,
) -> dict[str, object]:
    normalized_symbol: str | None = None
    symbol_filter = _clean_filter(symbol)
    if symbol_filter is not None:
        try:
            normalized_symbol = _normalize_market_symbol(symbol_filter)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid paper order filter") from exc

    normalized_strategy_id = _clean_filter(strategy_id)

    normalized_side: str | None = None
    side_filter = _clean_filter(side)
    if side_filter is not None:
        try:
            normalized_side = IntentSide(side_filter.lower()).value
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid paper order filter") from exc

    orders = order_repo.list_orders(
        limit=limit,
        offset=offset,
        symbol=normalized_symbol,
        strategy_id=normalized_strategy_id,
        side=normalized_side,
    )
    items = [
        {
            "id": order.id,
            "symbol": order.symbol,
            "side": order.side.value,
            "notional": order.notional,
            "price": order.price,
            "base_amount": order.base_amount,
            "fee": order.fee,
            "strategy_id": order.strategy_id,
            "request_id": order.request_id,
        }
        for order in orders
    ]
    return _paginated_response(items, limit=limit, offset=offset)


@app.get("/api/v1/paper/trades")
def paper_trades(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    symbol: str | None = None,
    strategy_id: str | None = None,
    side: str | None = None,
) -> dict[str, object]:
    return paper_orders(
        limit=limit,
        offset=offset,
        symbol=symbol,
        strategy_id=strategy_id,
        side=side,
    )


@app.get("/api/v1/strategies")
def strategies() -> list[dict[str, str | bool]]:
    return [{"id": "ma-crossover-paper", "mode": "paper", "enabled": False}]


@app.post("/api/v1/strategies/{strategy_id}/enable-paper")
def enable_paper_strategy(strategy_id: str) -> dict[str, str | bool]:
    event = AuditEvent(
        event_type="strategy.enable_paper",
        message="paper strategy enable requested",
        request_id=strategy_id,
        metadata={"strategy_id": strategy_id},
    )
    audit_repo.add(event)
    return {"id": strategy_id, "enabled": True, "mode": "paper"}


@app.post("/api/v1/strategies/{strategy_id}/disable")
def disable_strategy(strategy_id: str) -> dict[str, str | bool]:
    event = AuditEvent(
        event_type="strategy.disable",
        message="strategy disable requested",
        request_id=strategy_id,
        metadata={"strategy_id": strategy_id},
    )
    audit_repo.add(event)
    return {"id": strategy_id, "enabled": False}


@app.get("/api/v1/risk/status")
def risk_status() -> dict[str, str | bool]:
    settings = get_settings()
    risk = RiskEngine(kill_switch=settings.global_kill_switch)
    return {
        "status": "blocked" if risk.kill_switch else "active",
        "kill_switch": risk.kill_switch,
        "mode": settings.execution_mode.value,
    }


@app.post("/api/v1/risk/kill-switch")
def kill_switch() -> dict[str, str | bool]:
    event = AuditEvent(
        event_type="risk.kill_switch.requested",
        message="kill switch request received",
        request_id="kill-switch",
    )
    audit_repo.add(event)
    return {"status": "accepted", "kill_switch": True, "note": "set GLOBAL_KILL_SWITCH=true"}


@app.get("/api/v1/audit/events")
def audit_events(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    event_type: str | None = None,
    request_id: str | None = None,
    actor: str | None = None,
) -> dict[str, object]:
    events = audit_repo.list_events(
        limit=limit,
        offset=offset,
        event_type=_clean_filter(event_type),
        request_id=_clean_filter(request_id),
        actor=_clean_filter(actor),
    )
    items = [
        {
            "id": event.id,
            "event_type": event.event_type,
            "message": event.message,
            "request_id": event.request_id,
            "actor": event.actor,
            "metadata": event.metadata,
            "created_at": event.created_at.isoformat(),
        }
        for event in events
    ]
    return _paginated_response(items, limit=limit, offset=offset)


@app.post("/api/v1/paper/demo-order")
def demo_paper_order() -> dict[str, str | float]:
    intent = StrategyIntent(
        symbol="BTC/USDT",
        side=IntentSide.ENTER_LONG,
        notional=25,
        strategy_id="demo",
        reason="demo_order_endpoint",
    )
    risk = RiskEngine()
    order = paper_engine.execute(intent, price=50_000, risk=risk)
    order_repo.add(order)
    audit_repo.add(
        AuditEvent(
            event_type="paper.order.created",
            message="demo paper order created",
            request_id=order.request_id,
            metadata={"symbol": order.symbol, "notional": order.notional},
        )
    )
    return {
        "id": order.id,
        "symbol": order.symbol,
        "notional": order.notional,
        "price": order.price,
    }


@app.post("/api/v1/backtest/run")
def run_backtest(payload: BacktestRunIn) -> dict[str, BacktestValue]:
    normalized_symbol = _normalize_market_symbol(payload.symbol)
    strategy = MovingAverageCrossoverStrategy(
        symbol=normalized_symbol,
        fast=payload.fast,
        slow=payload.slow,
        notional=payload.notional,
    )
    engine = BacktestEngine(starting_usdt=payload.starting_usdt, starting_btc=payload.starting_btc)
    result = engine.run(
        strategy,
        candles=[
            Candle(
                timestamp=c.timestamp,
                open=c.open,
                high=c.high,
                low=c.low,
                close=c.close,
                volume=c.volume,
            )
            for c in payload.candles
        ],
    )
    persisted_run = backtest_repo.add(
        BacktestRun(
            strategy_id=result.strategy_id,
            symbol=normalized_symbol,
            candles_seen=result.candles_seen,
            orders_created=result.orders_created,
            ending_usdt=result.ending_usdt,
            ending_btc=result.ending_btc,
            metadata_json={
                "fast": payload.fast,
                "slow": payload.slow,
                "notional": payload.notional,
            },
        )
    )

    audit_repo.add(
        AuditEvent(
            event_type="backtest.completed",
            message="backtest run completed",
            request_id=persisted_run.id,
            metadata={"orders_created": result.orders_created, "candles_seen": result.candles_seen},
        )
    )
    return _serialize_backtest_run(persisted_run)


@app.get("/api/v1/backtests")
def list_backtests(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    symbol: str | None = None,
    strategy_id: str | None = None,
) -> dict[str, object]:
    normalized_symbol: str | None = None
    symbol_filter = _clean_filter(symbol)
    if symbol_filter is not None:
        try:
            normalized_symbol = _normalize_market_symbol(symbol_filter)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid backtest filter") from exc

    runs = backtest_repo.list_runs(
        limit=limit,
        offset=offset,
        symbol=normalized_symbol,
        strategy_id=_clean_filter(strategy_id),
    )
    items = [_serialize_backtest_run(run) for run in runs]
    return _paginated_response(items, limit=limit, offset=offset)


@app.get("/api/v1/backtests/{run_id}")
def backtest_detail(run_id: str) -> dict[str, BacktestValue]:
    run = backtest_repo.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="backtest run not found")
    return _serialize_backtest_run(run)


@app.get("/api/v1/safety/live-trading-disabled")
def live_trading_disabled() -> dict[str, str | bool]:
    settings = get_settings()
    safe = settings.execution_mode.value == "paper" and settings.live_trading_enabled is False
    return {
        "safe": safe,
        "execution_mode": settings.execution_mode.value,
        "live_trading_enabled": settings.live_trading_enabled,
        "proof": "paper_mode_enforced_and_live_flag_false",
    }
