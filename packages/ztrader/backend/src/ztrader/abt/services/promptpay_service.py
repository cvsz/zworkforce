"""// ZeaZDev [PromptPay Service] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 (Phase 4) //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

import base64
import hashlib
import hmac
import io
import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

import qrcode
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ztrader.abt.models import Transaction, Wallet


class PromptPayService:
    """Service for handling PromptPay QR code generation and payment processing"""

    def __init__(self):
        self.merchant_id = os.getenv("PROMPTPAY_MERCHANT_ID", "")
        self.webhook_secret = os.getenv("PROMPTPAY_WEBHOOK_SECRET", "")

    def generate_qr_code(self, amount: float, reference_id: str) -> str:
        """
        Generate PromptPay QR code for payment

        Args:
            amount: Payment amount in THB
            reference_id: Unique reference ID for this transaction

        Returns:
            Base64 encoded QR code image
        """
        # PromptPay QR format (simplified version)
        # In production, use proper EMVCo QR format
        payload = f"PROMPTPAY|{self.merchant_id}|{amount:.2f}|{reference_id}"

        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(payload)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        img_base64 = base64.b64encode(buffer.getvalue()).decode()

        return f"data:image/png;base64,{img_base64}"

    async def create_payment_intent(
        self,
        db: AsyncSession,
        user_id: int,
        amount: float,
        currency: str = "THB",
        description: str = "Account Top-up",
    ) -> Dict[str, Any]:
        """
        Create a payment intent and generate QR code

        Args:
            user_id: User ID making the payment
            amount: Payment amount
            currency: Payment currency (default: THB)
            description: Payment description

        Returns:
            Dict with QR code and transaction details
        """
        # Create transaction record
        transaction = Transaction(
            userId=user_id,
            type="TOP_UP",
            amount=amount,
            currency=currency,
            status="PENDING",
            paymentMethod="PROMPTPAY",
            metadataJson=json.dumps({"description": description}),
        )
        db.add(transaction)
        await db.flush()

        reference_id = f"TXN-{transaction.id}-{int(datetime.utcnow().timestamp())}"

        # Update transaction with reference ID
        transaction.referenceId = reference_id
        await db.flush()

        # Generate QR code
        qr_code_url = self.generate_qr_code(amount, reference_id)

        return {
            "transaction_id": transaction.id,
            "reference_id": reference_id,
            "amount": amount,
            "currency": currency,
            "qr_code_url": qr_code_url,
            "status": "PENDING",
            "created_at": transaction.createdAt.isoformat(),
        }

    def verify_webhook_signature(self, payload: str, signature: str) -> bool:
        """
        Verify webhook signature from payment gateway

        Args:
            payload: Webhook payload
            signature: Signature from payment gateway

        Returns:
            True if signature is valid, False otherwise
        """
        expected_signature = hmac.new(
            self.webhook_secret.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected_signature, signature)

    async def process_payment_callback(
        self,
        db: AsyncSession,
        reference_id: str,
        status: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process payment callback from payment gateway

        Args:
            reference_id: Transaction reference ID
            status: Payment status (SUCCESS, FAILED, PENDING)
            metadata: Additional metadata from gateway

        Returns:
            Dict with processing result
        """
        # Find transaction
        result = await db.execute(
            select(Transaction).where(Transaction.referenceId == reference_id)
        )
        transaction = result.scalar_one_or_none()

        if not transaction:
            return {"success": False, "error": "Transaction not found"}

        # Update transaction status
        transaction.status = status
        transaction.completedAt = datetime.utcnow() if status == "SUCCESS" else None
        transaction.metadataJson = json.dumps(
            {
                **json.loads(transaction.metadataJson or "{}"),
                "callback_metadata": metadata or {},
            }
        )
        await db.flush()

        # If successful, credit user wallet
        if status == "SUCCESS":
            await self._credit_wallet(db, transaction.userId, transaction.amount)

        return {
            "success": True,
            "transaction_id": transaction.id,
            "status": status,
            "amount": transaction.amount,
        }

    async def _credit_wallet(self, db: AsyncSession, user_id: int, amount: float):
        """Credit amount to user wallet"""
        result = await db.execute(
            select(Wallet).where(Wallet.userId == user_id)
        )
        wallet = result.scalar_one_or_none()

        if not wallet:
            wallet = Wallet(userId=user_id, balance=amount, currency="THB")
            db.add(wallet)
        else:
            wallet.balance += amount
        await db.flush()

    async def get_wallet_balance(
        self, db: AsyncSession, user_id: int
    ) -> Dict[str, Any]:
        """Get user wallet balance"""
        result = await db.execute(
            select(Wallet).where(Wallet.userId == user_id)
        )
        wallet = result.scalar_one_or_none()

        if not wallet:
            wallet = Wallet(userId=user_id, balance=0.0, currency="THB")
            db.add(wallet)
            await db.flush()

        return {
            "balance": wallet.balance,
            "currency": wallet.currency,
            "last_updated": wallet.updatedAt.isoformat(),
        }

    async def get_transaction_history(
        self, db: AsyncSession, user_id: int, limit: int = 50, offset: int = 0
    ) -> list:
        """Get user transaction history"""
        result = await db.execute(
            select(Transaction)
            .where(Transaction.userId == user_id)
            .order_by(Transaction.createdAt.desc())
            .limit(limit)
            .offset(offset)
        )
        transactions = result.scalars().all()

        return [
            {
                "id": txn.id,
                "type": txn.type,
                "amount": txn.amount,
                "currency": txn.currency,
                "status": txn.status,
                "payment_method": txn.paymentMethod,
                "reference_id": txn.referenceId,
                "created_at": txn.createdAt.isoformat(),
                "completed_at": (
                    txn.completedAt.isoformat() if txn.completedAt else None
                ),
            }
            for txn in transactions
        ]
