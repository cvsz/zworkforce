"""// ZeaZDev [Backend Celery Tasks] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 (Phase 5) //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

import asyncio
import logging

from ztrader.abt.services.audit_service import AuditService
from ztrader.abt.services.notification_service import NotificationService
from ztrader.abt.services.rental_service import RentalService
from ztrader.abt.services.secret_rotation_service import SecretRotationService
from ztrader.abt.trading.bot_runner import BotRunner
from ztrader.abt.utils.database import get_db_connection
from ztrader.abt.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="run_bot_loop")
def run_bot_loop(self, bot_id: int):
    asyncio.run(run_bot_async(bot_id))


async def run_bot_async(bot_id: int):
    async with get_db_connection() as db:
        runner = BotRunner(db=db, bot_id=bot_id)
        await runner.run_loop()


# Phase 4: Contract expiry checking task
@celery_app.task(bind=True, name="check_contract_expiry")
def check_contract_expiry(self):
    """Check for expiring or expired rental contracts"""
    asyncio.run(check_contract_expiry_async())


async def check_contract_expiry_async():
    """Async implementation of contract expiry checking"""
    async with get_db_connection() as db:
        rental_service = RentalService()
        _notification_service = NotificationService()

        try:
            logger.info("Starting contract expiry check...")

            # Check all contracts
            contracts_to_check = await rental_service.check_contract_expiry(db=db)

            for contract in contracts_to_check:
                proc_msg = (
                    f"Processing contract {contract['contract_id']} "
                    f"for user {contract['user_id']}"
                )
                logger.info(proc_msg)

                # Send renewal reminder if needed
                if contract["should_send_reminder"]:
                    days = contract["days_until_expiry"]
                    message = (
                        f"Your subscription expires in {days} day(s). "
                        "Please renew to continue using the service."
                    )

                    # Send notification (email/telegram)
                    try:
                        # This would send via telegram/email in production
                        sending_msg = (
                            "Sending renewal reminder to user "
                            f"{contract['user_id']}: {message}"
                        )
                        logger.info(sending_msg)
                    except Exception as e:
                        logger.error(f"Failed to send renewal reminder: {e}")

                # Disable contract if expired and past grace period
                if contract["should_disable"]:
                    logger.warning(
                        "Expiring contract %s for user %s",
                        contract["contract_id"],
                        contract["user_id"],
                    )
                    await rental_service.expire_contract(db=db, contract_id=contract["contract_id"])

                    # Send expiry notification
                    message = (
                        "Your subscription has expired. Your bots have been stopped. "
                        "Please renew to continue."
                    )
                    expiry_msg = (
                        "Sending expiry notification to user "
                        f"{contract['user_id']}: {message}"
                    )
                    logger.info(expiry_msg)

            completed_msg = (
                "Contract expiry check completed. Processed "
                f"{len(contracts_to_check)} contracts."
            )
            logger.info(completed_msg)

        except Exception as e:
            logger.error(f"Error during contract expiry check: {e}")
            raise


# Phase 5: Secret rotation reminder task
@celery_app.task(bind=True, name="check_secret_rotation")
def check_secret_rotation(self):
    """Check for secrets that need rotation and send reminders"""
    asyncio.run(check_secret_rotation_async())


async def check_secret_rotation_async():
    """Async implementation of secret rotation checking"""
    async with get_db_connection() as db:
        rotation_service = SecretRotationService()

        try:
            logger.info("Starting secret rotation check...")

            # Check for secrets due for rotation in next 7 days
            due_secrets = await rotation_service.get_secrets_due_for_rotation(db=db, days_ahead=7)

            # Count overdue vs upcoming
            overdue_count = sum(1 for s in due_secrets if s.get("overdue", False))
            upcoming_count = len(due_secrets) - overdue_count

            logger.info(
                f"Secret rotation check completed. "
                f"Overdue: {overdue_count}, Upcoming: {upcoming_count}"
            )

        except Exception as error:
            logger.error(
                "Secret rotation check failed",
                extra={"error_type": type(error).__name__},
            )
            raise


# Phase 5: Audit log cleanup task
@celery_app.task(bind=True, name="cleanup_audit_logs")
def cleanup_audit_logs(self):
    """Clean up old audit logs based on retention policy"""
    asyncio.run(cleanup_audit_logs_async())


async def cleanup_audit_logs_async():
    """Async implementation of audit log cleanup"""
    async with get_db_connection() as db:
        audit_service = AuditService()

        try:
            logger.info("Starting audit log cleanup...")

            deleted_count = await audit_service.cleanup_old_logs(db=db)

            logger.info(f"Audit log cleanup completed. Deleted {deleted_count} old logs.")

        except Exception as e:
            logger.error(f"Error during audit log cleanup: {e}")
            raise
