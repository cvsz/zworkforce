"""// ZeaZDev [Backend Service Exchange Connector] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 (Omega Scaffolding) //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

from typing import Optional

import ccxt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ztrader.abt.models import ExchangeKey
from ztrader.core.crypto_service import decrypt_data


class ExchangeConnector:
    @staticmethod
    async def for_exchange(db: AsyncSession, exchange_name: str, owner_id: Optional[int] = None):
        stmt = select(ExchangeKey).where(ExchangeKey.exchange == exchange_name)
        if owner_id:
            stmt = stmt.where(ExchangeKey.ownerId == owner_id)
        result = await db.execute(stmt)
        key = result.scalar_one_or_none()
        if not key:
            raise ValueError("No exchange key stored")
        api_key = decrypt_data(key.encrypted_key, key.iv_key)
        api_secret = decrypt_data(key.encrypted_secret, key.iv_secret)
        cls = getattr(ccxt, exchange_name)
        return cls({"apiKey": api_key, "secret": api_secret, "enableRateLimit": True})
