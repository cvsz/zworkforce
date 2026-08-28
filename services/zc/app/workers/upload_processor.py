import asyncio
import logging
from app.services.queue import queue_service

logger = logging.getLogger(__name__)

async def process_upload_event(payload: dict):
    """
    Handle background processing for file uploads.
    E.g. Virus scanning, indexing, format validation.
    """
    file_id = payload.get("file_id")
    object_key = payload.get("object_key")

    logger.info(f"Processing upload event for file_id: {file_id}, key: {object_key}")

    # Files remain quarantined until an external scanner publishes a signed
    # clean verdict. Never represent an unscanned object as safe.
    await queue_service.publish("upload.quarantined", {
        "file_id": file_id,
        "object_key": object_key,
        "status": "awaiting_security_scan",
    })

async def start_workers():
    """Start all background worker subscriptions."""
    await queue_service.connect()
    await queue_service.subscribe("upload.received", process_upload_event)
    logger.info("Upload processing workers started.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    async def run_forever() -> None:
        await start_workers()
        await asyncio.Event().wait()

    asyncio.run(run_forever())
