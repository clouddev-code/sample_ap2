"""ユーザー側エージェントとマーチャント側エージェントの簡易実装."""

from __future__ import annotations

from dataclasses import dataclass

from ap2.crypto import KeyPair
from ap2.mandates import CartItem, CartMandate, IntentMandate, SignedMandate


@dataclass
class UserAgent:
    """ユーザーの代理として Intent Mandate を発行するエージェント."""

    user_id: str
    keypair: KeyPair

    @classmethod
    def create(cls, user_id: str) -> "UserAgent":
        return cls(user_id=user_id, keypair=KeyPair.generate())

    def issue_intent(
        self,
        description: str,
        max_amount: float,
        currency: str = "USD",
        allowed_categories: list[str] | None = None,
        max_items: int = 1,
    ) -> SignedMandate:
        intent = IntentMandate(
            user_id=self.user_id,
            description=description,
            max_amount=max_amount,
            currency=currency,
            allowed_categories=allowed_categories or [],
            max_items=max_items,
        )
        return SignedMandate.issue(intent.to_payload(), self.keypair)


@dataclass
class MerchantAgent:
    """マーチャント側エージェント. Intent を受けて Cart Mandate を生成する."""

    merchant_id: str
    catalog: list[CartItem]
    keypair: KeyPair

    @classmethod
    def create(cls, merchant_id: str, catalog: list[CartItem]) -> "MerchantAgent":
        return cls(
            merchant_id=merchant_id, catalog=catalog, keypair=KeyPair.generate()
        )

    def propose_cart(
        self, signed_intent: SignedMandate, selected_skus: list[str]
    ) -> SignedMandate:
        intent_id = signed_intent.payload["mandate_id"]
        currency = signed_intent.payload["currency"]
        catalog_by_sku = {i.sku: i for i in self.catalog}

        items: list[CartItem] = []
        for sku in selected_skus:
            if sku not in catalog_by_sku:
                raise ValueError(f"SKU {sku} はカタログに存在しません")
            items.append(catalog_by_sku[sku])

        cart = CartMandate(
            intent_mandate_id=intent_id,
            merchant_id=self.merchant_id,
            items=items,
            currency=currency,
        )
        return SignedMandate.issue(cart.to_payload(), self.keypair)
