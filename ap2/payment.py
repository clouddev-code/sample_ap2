"""決済処理のモック.

実運用では Adyen / PayPal / x402 等のアダプタに差し替える.
本サンプルは Mandate チェーンの整合性を確認したうえで決済結果を生成する.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from ap2.mandates import SignedMandate
from ap2.validation import ValidationError, validate_cart_against_intent


@dataclass
class PaymentReceipt:
    payment_id: str
    cart_mandate_id: str
    intent_mandate_id: str
    amount: float
    currency: str
    status: Literal["SUCCESS", "FAILED"]
    reason: str | None
    timestamp: str


class PaymentProcessor:
    """Mandate チェーンを検証してから決済を確定する."""

    def __init__(self, processor_id: str = "mock-processor-001") -> None:
        self.processor_id = processor_id

    def execute(
        self, signed_intent: SignedMandate, signed_cart: SignedMandate
    ) -> PaymentReceipt:
        cart_payload = signed_cart.payload
        try:
            validate_cart_against_intent(signed_intent, signed_cart)
        except ValidationError as e:
            return PaymentReceipt(
                payment_id=f"pay_{uuid.uuid4().hex[:12]}",
                cart_mandate_id=cart_payload["mandate_id"],
                intent_mandate_id=cart_payload["intent_mandate_id"],
                amount=cart_payload["total_amount"],
                currency=cart_payload["currency"],
                status="FAILED",
                reason=str(e),
                timestamp=datetime.now(tz=timezone.utc).isoformat(),
            )

        return PaymentReceipt(
            payment_id=f"pay_{uuid.uuid4().hex[:12]}",
            cart_mandate_id=cart_payload["mandate_id"],
            intent_mandate_id=cart_payload["intent_mandate_id"],
            amount=cart_payload["total_amount"],
            currency=cart_payload["currency"],
            status="SUCCESS",
            reason=None,
            timestamp=datetime.now(tz=timezone.utc).isoformat(),
        )
