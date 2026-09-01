"""// ZeaZDev [Secret Rotation Service] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 (Phase 5) //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

import hashlib
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ztrader.abt.models import SecretRotation


class SecretRotationService:
    """Service for managing secret rotation"""

    def __init__(self):
        self.rotation_policy_days = int(os.getenv("SECRET_ROTATION_POLICY_DAYS", "90"))
        self.grace_period_days = int(
            os.getenv("SECRET_ROTATION_GRACE_PERIOD_DAYS", "7")
        )

    def hash_secret(self, secret: str) -> str:
        """
        Create a hash of the secret for verification (never store the actual secret)

        Args:
            secret: Secret value to hash

        Returns:
            SHA-256 hash of the secret
        """
        return hashlib.sha256(secret.encode()).hexdigest()

    async def create_rotation_record(
        self,
        db: AsyncSession,
        secret_type: str,
        secret_name: str,
        new_secret_value: str,
        rotated_by: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a rotation record when a secret is rotated

        Args:
            db: AsyncSession instance
            secret_type: Type of secret (DATABASE, ENCRYPTION_KEY, API_KEY,
                OAUTH_SECRET)
            secret_name: Identifier for the secret
            new_secret_value: New secret value (will be hashed, not stored)
            rotated_by: User ID who performed the rotation
            metadata: Additional information about the rotation

        Returns:
            Created rotation record
        """
        # Calculate next rotation date
        next_rotation = datetime.utcnow() + timedelta(days=self.rotation_policy_days)

        # Find previous rotation record
        result = await db.execute(
            select(SecretRotation).where(
                SecretRotation.secretType == secret_type,
                SecretRotation.secretName == secret_name,
                SecretRotation.status == "ACTIVE",
            )
        )
        previous = result.scalar_one_or_none()

        # Mark previous rotation as deprecated
        if previous:
            previous.status = "DEPRECATED"

        # Create new rotation record
        rotation = SecretRotation(
            secretType=secret_type,
            secretName=secret_name,
            rotatedBy=rotated_by,
            previousHash=previous.previousHash if previous else None,
            nextRotation=next_rotation,
            status="ACTIVE",
            metadataJson=str(metadata) if metadata else None,
        )
        db.add(rotation)
        await db.flush()

        return {
            "id": rotation.id,
            "secretType": rotation.secretType,
            "secretName": rotation.secretName,
            "rotatedAt": rotation.rotatedAt.isoformat(),
            "nextRotation": rotation.nextRotation.isoformat(),
            "status": rotation.status,
        }

    async def get_rotation_schedule(
        self, db: AsyncSession, secret_type: Optional[str] = None, include_deprecated: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get rotation schedule for all secrets or specific type

        Args:
            db: AsyncSession instance
            secret_type: Filter by secret type
            include_deprecated: Include deprecated rotations

        Returns:
            List of rotation schedules
        """
        conditions = []
        if secret_type:
            conditions.append(SecretRotation.secretType == secret_type)
        if not include_deprecated:
            conditions.append(SecretRotation.status == "ACTIVE")

        result = await db.execute(
            select(SecretRotation)
            .options(selectinload(SecretRotation.user))
            .where(*conditions)
            .order_by(SecretRotation.nextRotation.asc())
        )
        rotations = result.scalars().all()

        now = datetime.utcnow()

        return [
            {
                "id": r.id,
                "secretType": r.secretType,
                "secretName": r.secretName,
                "lastRotated": r.rotatedAt.isoformat(),
                "nextRotation": r.nextRotation.isoformat(),
                "daysUntilRotation": (r.nextRotation - now).days,
                "status": r.status,
                "rotatedBy": r.user.email if r.user else None,
            }
            for r in rotations
        ]

    async def get_rotation_history(
        self,
        db: AsyncSession,
        secret_type: Optional[str] = None,
        secret_name: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get rotation history

        Args:
            db: AsyncSession instance
            secret_type: Filter by secret type
            secret_name: Filter by secret name
            limit: Maximum number of records to return

        Returns:
            List of historical rotations
        """
        conditions = []
        if secret_type:
            conditions.append(SecretRotation.secretType == secret_type)
        if secret_name:
            conditions.append(SecretRotation.secretName == secret_name)

        result = await db.execute(
            select(SecretRotation)
            .options(selectinload(SecretRotation.user))
            .where(*conditions)
            .order_by(SecretRotation.rotatedAt.desc())
            .limit(limit)
        )
        rotations = result.scalars().all()

        return [
            {
                "id": r.id,
                "secretType": r.secretType,
                "secretName": r.secretName,
                "rotatedAt": r.rotatedAt.isoformat(),
                "rotatedBy": r.user.email if r.user else None,
                "status": r.status,
                "nextRotation": r.nextRotation.isoformat(),
            }
            for r in rotations
        ]

    async def get_secrets_due_for_rotation(
        self, db: AsyncSession, days_ahead: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Get secrets that are due for rotation within specified days

        Args:
            db: AsyncSession instance
            days_ahead: Number of days to look ahead

        Returns:
            List of secrets needing rotation
        """
        cutoff_date = datetime.utcnow() + timedelta(days=days_ahead)

        result = await db.execute(
            select(SecretRotation)
            .where(
                SecretRotation.status == "ACTIVE",
                SecretRotation.nextRotation <= cutoff_date,
            )
            .order_by(SecretRotation.nextRotation.asc())
        )
        rotations = result.scalars().all()

        now = datetime.utcnow()

        return [
            {
                "id": r.id,
                "secretType": r.secretType,
                "secretName": r.secretName,
                "lastRotated": r.rotatedAt.isoformat(),
                "nextRotation": r.nextRotation.isoformat(),
                "daysUntilRotation": (r.nextRotation - now).days,
                "overdue": r.nextRotation < now,
            }
            for r in rotations
        ]

    async def update_rotation_policy(
        self,
        db: AsyncSession,
        secret_type: str,
        secret_name: str,
        rotation_interval_days: int,
        grace_period_days: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Update the rotation policy for a specific secret

        Args:
            db: AsyncSession instance
            secret_type: Type of secret
            secret_name: Name of secret
            rotation_interval_days: New rotation interval in days
            grace_period_days: Grace period in days

        Returns:
            Updated rotation record
        """
        # Find active rotation
        result = await db.execute(
            select(SecretRotation).where(
                SecretRotation.secretType == secret_type,
                SecretRotation.secretName == secret_name,
                SecretRotation.status == "ACTIVE",
            )
        )
        rotation = result.scalar_one_or_none()

        if not rotation:
            raise ValueError(
                f"No active rotation found for {secret_type}:{secret_name}"
            )

        # Calculate new next rotation date
        rotation.nextRotation = rotation.rotatedAt + timedelta(days=rotation_interval_days)
        await db.flush()

        return {
            "id": rotation.id,
            "secretType": rotation.secretType,
            "secretName": rotation.secretName,
            "rotatedAt": rotation.rotatedAt.isoformat(),
            "nextRotation": rotation.nextRotation.isoformat(),
            "status": rotation.status,
        }

    async def mark_rotation_complete(
        self, db: AsyncSession, secret_type: str, secret_name: str
    ) -> Dict[str, Any]:
        """
        Mark a rotation as completed and create a new active record

        Args:
            db: AsyncSession instance
            secret_type: Type of secret
            secret_name: Name of secret

        Returns:
            Result of rotation completion
        """
        # Find active rotation
        result = await db.execute(
            select(SecretRotation).where(
                SecretRotation.secretType == secret_type,
                SecretRotation.secretName == secret_name,
                SecretRotation.status == "ACTIVE",
            )
        )
        rotation = result.scalar_one_or_none()

        if not rotation:
            raise ValueError(
                f"No active rotation found for {secret_type}:{secret_name}"
            )

        # Mark as rotated
        rotation.status = "ROTATED"
        await db.flush()

        return {
            "secretType": secret_type,
            "secretName": secret_name,
            "status": "ROTATED",
            "message": "Rotation marked as complete",
        }
