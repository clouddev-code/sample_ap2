"""リアルタイム購買フローのサンプル.

シナリオ: 「白いランニングシューズが欲しい」
  1. ユーザーエージェントが Intent Mandate を署名
  2. マーチャントエージェントが Cart Mandate を提案
  3. PaymentProcessor が両方を検証して決済
"""

from __future__ import annotations

import json

from ap2.agent import MerchantAgent, UserAgent
from ap2.mandates import CartItem
from ap2.payment import PaymentProcessor


def main() -> None:
    # 1. ユーザーエージェントが Intent を発行
    user = UserAgent.create(user_id="user-alice")
    signed_intent = user.issue_intent(
        description="白の新しいランニングシューズが欲しい",
        max_amount=180.00,
        currency="USD",
        allowed_categories=["shoes", "footwear"],
        max_items=1,
    )
    print("=== Intent Mandate ===")
    print(json.dumps(signed_intent.payload, indent=2, ensure_ascii=False))

    # 2. マーチャントエージェントを準備
    catalog = [
        CartItem(sku="SH-001", name="AirRun White", category="shoes", unit_price=149.0),
        CartItem(sku="SH-002", name="CloudFly Pro", category="shoes", unit_price=219.0),
        CartItem(sku="AC-010", name="Sport Socks", category="accessories", unit_price=12.0),
    ]
    merchant = MerchantAgent.create(merchant_id="acme-shoes", catalog=catalog)

    # 3. ユーザーが提示候補を承認したと想定し Cart を提案
    signed_cart = merchant.propose_cart(signed_intent, selected_skus=["SH-001"])
    print("\n=== Cart Mandate ===")
    print(json.dumps(signed_cart.payload, indent=2, ensure_ascii=False))

    # 4. 決済実行
    processor = PaymentProcessor()
    receipt = processor.execute(signed_intent, signed_cart)
    print("\n=== Payment Receipt ===")
    print(receipt)


if __name__ == "__main__":
    main()
