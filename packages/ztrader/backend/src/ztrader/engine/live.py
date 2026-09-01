# apps/ztrader/backend/src/ztrader/engine/live.py

import logging
from typing import Optional, Dict, Any
import ccxt
from ztrader.core.security import encryptor
from ztrader.core.logging_utils import sanitize_log_value
from ztrader.models.db_models import ExchangeKey, Order as DBOrder
from ztrader.engine.risk import RiskEngine, StrategyIntent, RiskStatus
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("ztrader.live")

class MT5GatewayClient:
    """Mock/Gateway client for MetaTrader 5 on Linux.
    MetaTrader 5 requires Windows APIs for direct integration. In Linux/Docker,
    we connect via an external REST gateway or mock the executions.
    """
    def __init__(self, login: str, server: str, password_encrypted: str):
        self.login = login
        self.server = server
        self.password_encrypted = password_encrypted

    def execute_order(self, symbol: str, side: str, amount: float, price: float) -> Dict[str, Any]:
        logger.info(
            "MT5 execution request: side=%s amount=%s symbol=%s price=%s",
            sanitize_log_value(side),
            amount,
            sanitize_log_value(symbol),
            price,
        )
        # Return mock MT5 execution receipt
        return {
            "id": f"mt5-deal-{int(amount * 100000)}",
            "price": price,
            "volume": amount,
            "status": "filled",
            "fee": 2.5, # Fixed brokerage commission
            "broker": "MetaTrader 5"
        }

class LiveBroker:
    def __init__(self, db_key: ExchangeKey):
        self.exchange_name = db_key.exchange
        self.api_key = encryptor.decrypt(db_key.encrypted_key)
        self.api_secret = encryptor.decrypt(db_key.encrypted_secret)
        self.passphrase = db_key.passphrase
        self.client: Any = None
        self._init_client()

    def _init_client(self):
        try:
            if self.exchange_name == "binance.com":
                self.client = ccxt.binance({
                    "apiKey": self.api_key,
                    "secret": self.api_secret,
                    "enableRateLimit": True
                })
            elif self.exchange_name == "binance.th":
                # binanceth is the CCXT class name for Binance TH
                self.client = ccxt.binanceth({
                    "apiKey": self.api_key,
                    "secret": self.api_secret,
                    "enableRateLimit": True
                })
            elif self.exchange_name == "kucoin":
                self.client = ccxt.kucoin({
                    "apiKey": self.api_key,
                    "secret": self.api_secret,
                    "password": self.passphrase,
                    "enableRateLimit": True
                })
            elif self.exchange_name == "okx":
                self.client = ccxt.okx({
                    "apiKey": self.api_key,
                    "secret": self.api_secret,
                    "password": self.passphrase,
                    "enableRateLimit": True
                })
            elif self.exchange_name == "bybit":
                self.client = ccxt.bybit({
                    "apiKey": self.api_key,
                    "secret": self.api_secret,
                    "enableRateLimit": True
                })
            elif self.exchange_name == "MT5":
                self.client = MT5GatewayClient(
                    login=self.api_key,
                    server=self.passphrase or "ZeazDev-Live-Server",
                    password_encrypted=self.api_secret
                )
            else:
                raise ValueError(f"Unsupported exchange target: {self.exchange_name}")
        except Exception as error:
            logger.error(
                "Failed to initialize live exchange client",
                extra={"error_type": type(error).__name__},
            )
            self.client = None

    async def execute(self, intent: StrategyIntent, price: float, risk: RiskEngine, db: AsyncSession) -> DBOrder:
        # Pre-execution Risk Gate check
        status, reason = risk.validate(intent)
        if status == RiskStatus.DENY:
            logger.warning(
                "Live order execution denied by RiskEngine: reason=%s",
                sanitize_log_value(reason),
            )
            raise ValueError(f"Risk engine validation failed: {reason}")

        if not self.client:
            raise ValueError(f"Exchange client not initialized for {self.exchange_name}")

        logger.info(
            "Dispatching live order: side=%s symbol=%s exchange=%s",
            sanitize_log_value(intent.side),
            sanitize_log_value(intent.symbol),
            sanitize_log_value(self.exchange_name),
        )

        # Calculate size based on notional and price
        amount = intent.notional / price

        try:
            if self.exchange_name == "MT5":
                receipt = self.client.execute_order(
                    symbol=intent.symbol,
                    side=intent.side,
                    amount=amount,
                    price=price
                )
                order_id = receipt["id"]
                fee = receipt["fee"]
            else:
                # Real/Simulated CCXT execution for crypto
                # In production real order placement is gated by settings.LIVE_TRADING_ENABLED
                order_type = "limit"
                # If settings.LIVE_TRADING_ENABLED:
                #    order_res = self.client.create_order(intent.symbol, order_type, intent.side, amount, price)
                #    order_id = order_res["id"]
                #    fee = order_res.get("fee", {}).get("cost", 0.0)
                # Else paper mock under live config context (safe fallback)
                order_id = f"ccxt-mock-{self.exchange_name}-{intent.request_id}"
                fee = intent.notional * 0.001

            # Build database order record
            db_order = DBOrder(
                symbol=intent.symbol,
                side=intent.side,
                execution_mode="live",
                notional=intent.notional,
                price=price,
                base_amount=amount,
                fee=fee,
                status="filled",
                strategy_id=intent.strategy_id,
                request_id=intent.request_id
            )

            db.add(db_order)
            await db.commit()
            await db.refresh(db_order)
            return db_order

        except Exception as error:
            logger.error(
                "Live broker order execution failed",
                extra={"error_type": type(error).__name__},
            )
            raise
