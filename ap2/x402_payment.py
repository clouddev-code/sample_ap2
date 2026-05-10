"""AP2 Mandate を検証したうえで x402 (HTTP 402) 経由で実決済する PaymentProcessor.

設計のポイント:
  - AP2 Mandate (Ed25519) と x402 決済 (EVM 署名) は層が違う:
      Mandate = "ユーザーが何をエージェントに許可したか" の証跡
      x402    = ステーブルコインの実際の送金
  - 本クラスは Mandate チェーンを先に検証し, OK なら x402 で支払う.
  - 失敗時は Mandate 段階か決済段階かを区別して PaymentReceipt に reason として残す.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from x402 import x402ClientSync
from x402.http.clients.requests import x402_requests
from x402.mechanisms.evm.exact.register import register_exact_evm_client

from ap2.cdp_signer import CdpEvmAccount
from ap2.mandates import SignedMandate
from ap2.payment import PaymentReceipt
from ap2.validation import ValidationError, validate_cart_against_intent


@dataclass
class X402Settlement:
    """x402 決済の結果."""

    http_status: int
    response_body: str
    settlement_header: str | None
    network: str
    payer: str


class X402PaymentProcessor:
    """Mandate 検証 + x402 によるステーブルコイン決済."""

    def __init__(
        self,
        account: CdpEvmAccount,
        network: str | None = None,
    ) -> None:
        self.account = account
        self.network = network or os.getenv("X402_NETWORK", "base-sepolia")
        self.client = x402ClientSync()
        register_exact_evm_client(self.client, account.signer, networks=[self.network])
        self.session = x402_requests(self.client)

    def execute(
        self,
        signed_intent: SignedMandate,
        signed_cart: SignedMandate,
        merchant_paywall_url: str,
    ) -> PaymentReceipt:
        """Intent / Cart を検証 → x402 paywall を叩いてステーブルコイン送金."""
        cart_payload = signed_cart.payload
        try:
            validate_cart_against_intent(signed_intent, signed_cart)
        except ValidationError as e:
            return self._failed(cart_payload, f"Mandate validation failed: {e}")

        try:
            response = self.session.get(
                merchant_paywall_url,
                headers={
                    "X-AP2-Intent-Id": signed_intent.payload["mandate_id"],
                    "X-AP2-Cart-Id": cart_payload["mandate_id"],
                },
                timeout=60,
            )
        except Exception as e:
            return self._failed(cart_payload, f"x402 request error: {e}")

        if response.status_code != 200:
            return self._failed(
                cart_payload,
                f"x402 settlement failed: status={response.status_code} body={response.text[:200]}",
            )

        return PaymentReceipt(
            payment_id=f"pay_{uuid.uuid4().hex[:12]}",
            cart_mandate_id=cart_payload["mandate_id"],
            intent_mandate_id=cart_payload["intent_mandate_id"],
            amount=cart_payload["total_amount"],
            currency=cart_payload["currency"],
            status="SUCCESS",
            reason=f"x402 ok | tx_header={response.headers.get('x-payment-response', '')[:60]}",
            timestamp=datetime.now(tz=timezone.utc).isoformat(),
        )

    @staticmethod
    def _failed(cart_payload: dict, reason: str) -> PaymentReceipt:
        return PaymentReceipt(
            payment_id=f"pay_{uuid.uuid4().hex[:12]}",
            cart_mandate_id=cart_payload["mandate_id"],
            intent_mandate_id=cart_payload["intent_mandate_id"],
            amount=cart_payload["total_amount"],
            currency=cart_payload["currency"],
            status="FAILED",
            reason=reason,
            timestamp=datetime.now(tz=timezone.utc).isoformat(),
        )
