"""Cart Mandate が Intent Mandate の制約を満たすかを検証する.

AP2 の認可モデルの中核. ここで通すか落とすかが最終的なユーザーの権限委譲の境界線.
"""

from __future__ import annotations

from ap2.mandates import CartMandate, IntentMandate, SignedMandate


class ValidationError(Exception):
    """Mandate 検証失敗を表す例外."""


def _payload_to_intent(payload: dict) -> IntentMandate:
    fields = {k: v for k, v in payload.items() if k != "type"}
    return IntentMandate(**fields)


def _payload_to_cart(payload: dict) -> CartMandate:
    from ap2.mandates import CartItem

    items = [CartItem(**i) for i in payload["items"]]
    return CartMandate(
        intent_mandate_id=payload["intent_mandate_id"],
        merchant_id=payload["merchant_id"],
        items=items,
        currency=payload["currency"],
        mandate_id=payload["mandate_id"],
        issued_at=payload["issued_at"],
        expires_at=payload["expires_at"],
    )


def validate_cart_against_intent(
    signed_intent: SignedMandate, signed_cart: SignedMandate
) -> None:
    """Cart Mandate が Intent Mandate の条件を満たすか検証する.

    検証に失敗した場合は ValidationError を送出する.
    """
    # 1. 署名検証
    if not signed_intent.verify():
        raise ValidationError("Intent Mandate の署名が無効です")
    if not signed_cart.verify():
        raise ValidationError("Cart Mandate の署名が無効です")

    # 2. 有効期限
    if signed_intent.is_expired():
        raise ValidationError("Intent Mandate は有効期限切れです")
    if signed_cart.is_expired():
        raise ValidationError("Cart Mandate は有効期限切れです")

    intent = _payload_to_intent(signed_intent.payload)
    cart = _payload_to_cart(signed_cart.payload)

    # 3. Intent <-> Cart のリンク整合性
    if cart.intent_mandate_id != intent.mandate_id:
        raise ValidationError(
            f"Cart が参照する intent_mandate_id ({cart.intent_mandate_id}) は "
            f"提示された Intent ({intent.mandate_id}) と一致しません"
        )

    # 4. 通貨一致
    if cart.currency != intent.currency:
        raise ValidationError(
            f"通貨不一致: intent={intent.currency} cart={cart.currency}"
        )

    # 5. ビジネス制約 (上限金額・数量・カテゴリ) の検証
    if cart.total_amount > intent.max_amount:
        raise ValidationError(
            f"合計金額が上限を超過: cart={cart.total_amount} {cart.currency} "
            f"> intent.max_amount={intent.max_amount} {intent.currency}"
        )

    total_quantity = sum(item.quantity for item in cart.items)
    if total_quantity > intent.max_items:
        raise ValidationError(
            f"数量が上限を超過: cart={total_quantity} > "
            f"intent.max_items={intent.max_items}"
        )

    if intent.allowed_categories:
        allowed = set(intent.allowed_categories)
        disallowed = [i.category for i in cart.items if i.category not in allowed]
        if disallowed:
            raise ValidationError(
                f"許可されていないカテゴリが含まれています: {disallowed} "
                f"(allowed={intent.allowed_categories})"
            )
