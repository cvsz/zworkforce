"""// ZeaZDev [Rental Service] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 (Phase 4) //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ztrader.abt.models import BotRun, RentalContract


class RentalService:
    """Service for managing rental contracts and subscriptions"""

    # Subscription plans configuration
    PLANS = {
        "BASIC": {
            "name": "Basic Plan",
            "price": 499,
            "currency": "THB",
            "duration_days": 30,
            "max_bots": 2,
            "features": ["basic_strategies", "email_support"],
        },
        "PREMIUM": {
            "name": "Premium Plan",
            "price": 1499,
            "currency": "THB",
            "duration_days": 30,
            "max_bots": 10,
            "features": [
                "advanced_strategies",
                "telegram_notifications",
                "portfolio_aggregation",
                "priority_support",
            ],
        },
        "ENTERPRISE": {
            "name": "Enterprise Plan",
            "price": 4999,
            "currency": "THB",
            "duration_days": 30,
            "max_bots": -1,  # unlimited
            "features": [
                "custom_strategies",
                "plugin_support",
                "dedicated_support",
                "api_access",
                "multi_account_portfolio",
                "backtesting",
                "paper_trading",
            ],
        },
    }

    async def get_user_contract(
        self, db: AsyncSession, user_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get user's current rental contract"""
        result = await db.execute(
            select(RentalContract)
            .where(RentalContract.userId == user_id)
            .order_by(RentalContract.createdAt.desc())
        )
        contract = result.scalar_one_or_none()

        if not contract:
            return None

        features = json.loads(contract.features) if contract.features else []

        return {
            "id": contract.id,
            "plan": contract.plan,
            "status": contract.status,
            "expiry": contract.expiry.isoformat(),
            "grace_period_days": contract.gracePeriodDays,
            "auto_renew": contract.autoRenew,
            "features": features,
            "created_at": contract.createdAt.isoformat(),
            "renewed_at": (
                contract.renewedAt.isoformat() if contract.renewedAt else None
            ),
            "is_expired": datetime.utcnow() > contract.expiry,
            "days_until_expiry": (contract.expiry - datetime.utcnow()).days,
        }

    async def create_contract(
        self, db: AsyncSession, user_id: int, plan: str, auto_renew: bool = False
    ) -> Dict[str, Any]:
        """Create a new rental contract"""
        if plan not in self.PLANS:
            raise ValueError(f"Invalid plan: {plan}")

        plan_config = self.PLANS[plan]
        expiry = datetime.utcnow() + timedelta(days=plan_config["duration_days"])

        contract = RentalContract(
            userId=user_id,
            plan=plan,
            expiry=expiry,
            status="ACTIVE",
            gracePeriodDays=3,
            autoRenew=auto_renew,
            features=json.dumps(plan_config["features"]),
        )
        db.add(contract)
        await db.flush()

        return {
            "id": contract.id,
            "plan": plan,
            "status": contract.status,
            "expiry": contract.expiry.isoformat(),
            "price": plan_config["price"],
            "currency": plan_config["currency"],
        }

    async def renew_contract(
        self, db: AsyncSession, user_id: int, plan: Optional[str] = None
    ) -> Dict[str, Any]:
        """Renew user's contract (optionally upgrade/downgrade)"""
        result = await db.execute(
            select(RentalContract)
            .where(RentalContract.userId == user_id)
            .order_by(RentalContract.createdAt.desc())
        )
        current_contract = result.scalar_one_or_none()

        if not current_contract:
            raise ValueError("No active contract found")

        new_plan = plan or current_contract.plan

        if new_plan not in self.PLANS:
            raise ValueError(f"Invalid plan: {new_plan}")

        plan_config = self.PLANS[new_plan]

        base_date = (
            current_contract.expiry
            if current_contract.status == "ACTIVE"
            and datetime.utcnow() < current_contract.expiry
            else datetime.utcnow()
        )
        new_expiry = base_date + timedelta(days=plan_config["duration_days"])

        current_contract.plan = new_plan
        current_contract.expiry = new_expiry
        current_contract.status = "ACTIVE"
        current_contract.renewedAt = datetime.utcnow()
        current_contract.features = json.dumps(plan_config["features"])
        await db.flush()

        return {
            "id": current_contract.id,
            "plan": new_plan,
            "status": current_contract.status,
            "expiry": current_contract.expiry.isoformat(),
            "price": plan_config["price"],
            "currency": plan_config["currency"],
        }

    async def check_contract_expiry(
        self, db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """
        Check for expiring/expired contracts
        Returns list of contracts that need attention
        """
        now = datetime.utcnow()

        result = await db.execute(
            select(RentalContract).where(
                RentalContract.status == "ACTIVE",
                RentalContract.expiry <= now + timedelta(days=7),
            )
        )
        contracts = result.scalars().all()

        results = []
        for contract in contracts:
            days_until_expiry = (contract.expiry - now).days
            is_expired = now > contract.expiry
            in_grace_period = (
                is_expired
                and (now - contract.expiry).days <= contract.gracePeriodDays
            )

            results.append(
                {
                    "contract_id": contract.id,
                    "user_id": contract.userId,
                    "plan": contract.plan,
                    "expiry": contract.expiry.isoformat(),
                    "days_until_expiry": days_until_expiry,
                    "is_expired": is_expired,
                    "in_grace_period": in_grace_period,
                    "should_send_reminder": days_until_expiry in [7, 3, 1]
                    and not is_expired,
                    "should_disable": is_expired and not in_grace_period,
                }
            )

        return results

    async def expire_contract(
        self, db: AsyncSession, contract_id: int
    ) -> Dict[str, Any]:
        """Mark a contract as expired and disable user's bots"""
        result = await db.execute(
            select(RentalContract).where(RentalContract.id == contract_id)
        )
        contract = result.scalar_one_or_none()

        contract.status = "EXPIRED"

        await db.execute(
            update(BotRun)
            .where(BotRun.userId == contract.userId, BotRun.status == "RUNNING")
            .values(status="STOPPED", stoppedAt=datetime.utcnow())
        )
        await db.flush()

        return {
            "contract_id": contract.id,
            "user_id": contract.userId,
            "status": contract.status,
            "bots_stopped": True,
        }

    async def has_feature(
        self, db: AsyncSession, user_id: int, feature_name: str
    ) -> bool:
        """Check if user has access to a specific feature"""
        result = await db.execute(
            select(RentalContract)
            .where(RentalContract.userId == user_id, RentalContract.status == "ACTIVE")
            .order_by(RentalContract.createdAt.desc())
        )
        contract = result.scalar_one_or_none()

        if not contract:
            return False

        now = datetime.utcnow()
        if now > contract.expiry:
            grace_period_end = contract.expiry + timedelta(
                days=contract.gracePeriodDays
            )
            if now > grace_period_end:
                return False

        features = json.loads(contract.features) if contract.features else []
        return feature_name in features

    def get_plan_info(self, plan: str) -> Optional[Dict[str, Any]]:
        """Get information about a subscription plan"""
        return self.PLANS.get(plan)

    def list_all_plans(self) -> List[Dict[str, Any]]:
        """List all available subscription plans"""
        return [
            {"plan_id": plan_id, **plan_info}
            for plan_id, plan_info in self.PLANS.items()
        ]
