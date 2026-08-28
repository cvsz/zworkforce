import os
import json
import logging
from typing import Callable, Awaitable
import nats
from nats.js.api import RetentionPolicy

logger = logging.getLogger(__name__)

class QueueService:
    def __init__(self):
        self.nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
        self.nc = None
        self.js = None
        self.stream_name = "WIRE_EVENTS"

    async def connect(self):
        """Connect to NATS and initialize JetStream."""
        try:
            self.nc = await nats.connect(self.nats_url)
            self.js = self.nc.jetstream()

            # Ensure stream exists
            try:
                await self.js.stream_info(self.stream_name)
            except nats.js.errors.NotFoundError:
                await self.js.add_stream(
                    name=self.stream_name,
                    subjects=[f"{self.stream_name}.*"],
                    retention=RetentionPolicy.WORK_QUEUE
                )
                logger.info(f"Created NATS JetStream: {self.stream_name}")
            logger.info("Connected to NATS JetStream successfully.")
        except Exception as e:
            logger.error(f"Failed to connect to NATS: {e}")
            raise

    async def publish(self, subject: str, payload: dict):
        """Publish a message to JetStream."""
        if not self.js:
            raise RuntimeError("NATS is not connected; refusing to lose an event")

        full_subject = f"{self.stream_name}.{subject}"
        data = json.dumps(payload).encode()
        await self.js.publish(full_subject, data)
        logger.debug(f"Published to {full_subject}")

    async def subscribe(self, subject: str, handler: Callable[[dict], Awaitable[None]]):
        """Subscribe to a subject and process messages."""
        if not self.js:
            logger.warning("NATS not connected. Cannot subscribe.")
            return

        full_subject = f"{self.stream_name}.{subject}"

        async def message_wrapper(msg):
            try:
                data = json.loads(msg.data.decode())
                await handler(data)
                await msg.ack()
            except Exception as e:
                logger.error(f"Error processing message from {full_subject}: {e}")
                await msg.nak()

        await self.js.subscribe(full_subject, cb=message_wrapper, queue="workers")
        logger.info(f"Subscribed to {full_subject} via queue group 'workers'")

    async def close(self):
        if self.nc:
            await self.nc.close()

queue_service = QueueService()
