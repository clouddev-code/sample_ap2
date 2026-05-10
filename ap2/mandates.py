"""Intent Mandate / Cart Mandate のデータモデル.

AP2 では 2 種類の Mandate を VC として署名する:
  - Intent Mandate: ユーザーの意図 (条件・上限) を捕捉
  - Cart Mandate:   実際に購入する商品とその合計を確定

それぞれ署名後は SignedMandate にラップされ、エージェント間で受け渡される.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from ap2.crypto import KeyPair, sign_payload, verify_signature


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _expiry_iso(minutes: int) -> str:
    return (datetime.now(tz=timezone.utc) + timedelta(minutes=minutes)).isoformat()


@dataclass
class IntentMandate:
    """ユーザーの意図を表す Mandate.

    Attributes:
        mandate_id: 一意識別子.
        user_id: 発行ユーザー.
        description: 自然言語のリクエスト ("白の新しいランニングシューズを買って").
        max_amount: 上限金額 (通貨単位は currency).
        currency: ISO 4217 通貨コード.
        allowed_categories: 許容カテゴリのキーワード.
        max_items: 最大数量.
        issued_at: 発行時刻 (ISO8601, UTC).
        expires_at: 有効期限.
    """

    user_id: str
    description: str
    max_amount: float
    currency: str = "USD"
    allowed_categories: list[str] = field(default_factory=list)
    max_items: int = 1
    mandate_id: str = field(default_factory=lambda: f"intent_{uuid.uuid4().hex[:12]}")
    issued_at: str = field(default_factory=_now_iso)
    expires_at: str = field(default_factory=lambda: _expiry_iso(60))

    def to_payload(self) -> dict[str, Any]:
        return {"type": "IntentMandate", **asdict(self)}


@dataclass
class CartItem:
    sku: str
    name: str
    category: str
    unit_price: float
    quantity: int = 1

    @property
    def subtotal(self) -> float:
        return round(self.unit_price * self.quantity, 2)


@dataclass
class CartMandate:
    """マーチャントが提示する具体的なカート.

    intent_mandate_id を必ず参照し、Intent → Cart の連鎖を保つ.
    """

    intent_mandate_id: str
    merchant_id: str
    items: list[CartItem]
    currency: str = "USD"
    mandate_id: str = field(default_factory=lambda: f"cart_{uuid.uuid4().hex[:12]}")
    issued_at: str = field(default_factory=_now_iso)
    expires_at: str = field(default_factory=lambda: _expiry_iso(15))

    @property
    def total_amount(self) -> float:
        return round(sum(i.subtotal for i in self.items), 2)

    def to_payload(self) -> dict[str, Any]:
        return {
            "type": "CartMandate",
            "mandate_id": self.mandate_id,
            "intent_mandate_id": self.intent_mandate_id,
            "merchant_id": self.merchant_id,
            "currency": self.currency,
            "items": [asdict(i) for i in self.items],
            "total_amount": self.total_amount,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
        }


@dataclass
class SignedMandate:
    """ペイロード + 署名 + 公開鍵 をひとまとめにした VC 風オブジェクト."""

    payload: dict[str, Any]
    signature: str
    issuer_public_key: str

    @classmethod
    def issue(cls, payload: dict[str, Any], keypair: KeyPair) -> "SignedMandate":
        return cls(
            payload=payload,
            signature=sign_payload(payload, keypair),
            issuer_public_key=keypair.public_key_b64(),
        )

    def verify(self) -> bool:
        return verify_signature(self.payload, self.signature, self.issuer_public_key)

    def is_expired(self) -> bool:
        expires = self.payload.get("expires_at")
        if not expires:
            return False
        return datetime.fromisoformat(expires) < datetime.now(tz=timezone.utc)
