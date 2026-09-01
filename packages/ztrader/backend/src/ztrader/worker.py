# apps/ztrader/backend/src/ztrader/worker.py

import logging
from celery import Celery
from ztrader.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ztrader.worker")

# Initialize Celery app
celery_app = Celery(
    "ztrader",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

# Optional configurations
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

@celery_app.task(name="ztrader.worker.execute_strategy_loop")
def execute_strategy_loop(strategy_name: str, symbol: str, notional: float) -> str:
    """Periodic task that fetches latest market candles, generates trading intents,
    gates them through the risk engine, and runs simulated or live broker execution."""
    logger.info(f"Running strategy loop for {strategy_name} on {symbol} with notional {notional}")

    # In production, this task would:
    # 1. Fetch latest candles from exchange or local database buffer
    # 2. Instantiate Strategy class (e.g. MovingAverageCrossoverStrategy)
    # 3. Call generate_intent(candles)
    # 4. Instantiate RiskEngine and validate intent
    # 5. On ALLOW: Dispatch order to PaperExecutionEngine or CCXT Live Broker
    # 6. Save order and audit events to PostgreSQL database via SQLAlchemy

    return f"Strategy loop completed for {strategy_name} on {symbol}"

if __name__ == "__main__":
    celery_app.worker_main(["worker", "--loglevel=info"])
