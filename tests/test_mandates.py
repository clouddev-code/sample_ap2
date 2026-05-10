"""Mandate 周りのユニットテスト."""

from __future__ import annotations

import pytest

from ap2.agent import MerchantAgent, UserAgent
from ap2.crypto import KeyPair, sign_payload, verify_signature
from ap2.mandates import CartItem, IntentMandate, SignedMandate
from ap2.payment import PaymentProcessor
from ap2.validation import ValidationError, validate_cart_against_intent


def _make_user_and_merchant():
    user = UserAgent.create(user_id="u-1")
    catalog = [
        CartItem(sku="A", name="Shoe", category="shoes", unit_price=100.0),
        CartItem(sku="B", name="Shirt", category="apparel", unit_price=50.0),
    ]
    merchant = MerchantAgent.create(merchant_id="m-1", catalog=catalog)
    return user, merchant


def test_signature_roundtrip():
    kp = KeyPair.generate()
    payload = {"foo": 1, "bar": "baz"}
    sig = sign_payload(payload, kp)
    assert verify_signature(payload, sig, kp.public_key_b64()) is True


def test_signature_tamper_detected():
    kp = KeyPair.generate()
    payload = {"foo": 1}
    sig = sign_payload(payload, kp)
    tampered = {"foo": 2}
    assert verify_signature(tampered, sig, kp.public_key_b64()) is False


def test_payment_success_within_constraints():
    user, merchant = _make_user_and_merchant()
    intent = user.issue_intent(
        description="買って",
        max_amount=200.0,
        allowed_categories=["shoes"],
        max_items=1,
    )
    cart = merchant.propose_cart(intent, selected_skus=["A"])
    receipt = PaymentProcessor().execute(intent, cart)
    assert receipt.status == "SUCCESS", receipt.reason


def test_payment_rejected_when_over_max_amount():
    user, merchant = _make_user_and_merchant()
    intent = user.issue_intent(
        description="安く買って",
        max_amount=80.0,
        allowed_categories=["shoes"],
        max_items=1,
    )
    cart = merchant.propose_cart(intent, selected_skus=["A"])  # 100 USD > 80
    receipt = PaymentProcessor().execute(intent, cart)
    assert receipt.status == "FAILED"


def test_payment_rejected_when_disallowed_category():
    user, merchant = _make_user_and_merchant()
    intent = user.issue_intent(
        description="靴を買って",
        max_amount=200.0,
        allowed_categories=["shoes"],
        max_items=2,
    )
    cart = merchant.propose_cart(intent, selected_skus=["B"])  # apparel
    receipt = PaymentProcessor().execute(intent, cart)
    assert receipt.status == "FAILED"


def test_payment_rejected_when_too_many_items():
    user, merchant = _make_user_and_merchant()
    intent = user.issue_intent(
        description="1 個だけ",
        max_amount=500.0,
        allowed_categories=["shoes"],
        max_items=1,
    )
    cart = merchant.propose_cart(intent, selected_skus=["A", "A"])
    receipt = PaymentProcessor().execute(intent, cart)
    assert receipt.status == "FAILED"


def test_validation_rejects_unlinked_cart():
    user, merchant = _make_user_and_merchant()
    intent = user.issue_intent(
        description="買って",
        max_amount=500.0,
        allowed_categories=["shoes"],
        max_items=1,
    )
    cart = merchant.propose_cart(intent, selected_skus=["A"])
    # cart の intent_mandate_id を別 ID に書き換え
    cart.payload["intent_mandate_id"] = "intent_does_not_exist"
    # ペイロードを書き換えると署名はもう一致しない -> 署名検証で落ちる
    with pytest.raises(ValidationError):
        validate_cart_against_intent(intent, cart)
