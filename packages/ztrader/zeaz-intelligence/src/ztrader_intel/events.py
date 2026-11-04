from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from .store import normalize_tenant_id


class EventBus:
    def __init__(self) -> None:
        self._subscribers_by_tenant: dict[str, set[asyncio.Queue[str]]] = {}

    async def publish(self, message: str, tenant_id: str = "default") -> None:
        scoped_tenant = normalize_tenant_id(tenant_id)
        subscribers = self._subscribers_by_tenant.get(scoped_tenant, set())
        for queue in tuple(subscribers):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            await queue.put(message)

    async def stream(self, tenant_id: str = "default") -> AsyncIterator[str]:
        scoped_tenant = normalize_tenant_id(tenant_id)
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=100)
        bucket = self._subscribers_by_tenant.setdefault(scoped_tenant, set())
        bucket.add(queue)
        try:
            while True:
                message = await queue.get()
                yield message
        finally:
            bucket.discard(queue)
            if not bucket:
                self._subscribers_by_tenant.pop(scoped_tenant, None)


event_bus = EventBus()
