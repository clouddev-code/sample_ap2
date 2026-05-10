"""委任タスクフローのサンプル.

シナリオ: 「コンサートチケットが発売されたら自動で 2 枚買って. 1 枚 250 USD まで」
  - ユーザーは事前に Intent Mandate に署名 (条件付き).
  - エージェントが在庫を検知したら Cart を生成し決済.
  - 上限超過時には PaymentProcessor が拒否することを確認する.
"""

from __future__ import annotations

from ap2.agent import MerchantAgent, UserAgent
from ap2.mandates import CartItem
from ap2.payment import PaymentProcessor


def run(scenario: str, signed_intent, merchant: MerchantAgent, skus: list[str]):
    cart = merchant.propose_cart(signed_intent, selected_skus=skus)
    receipt = PaymentProcessor().execute(signed_intent, cart)
    print(f"--- {scenario} ---")
    print(f"  total = {receipt.amount} {receipt.currency}")
    print(f"  status = {receipt.status}")
    if receipt.reason:
        print(f"  reason = {receipt.reason}")
    print()


def main() -> None:
    user = UserAgent.create(user_id="user-bob")
    signed_intent = user.issue_intent(
        description="コンサートチケットが発売されたら自動で 2 枚買う",
        max_amount=500.00,
        currency="USD",
        allowed_categories=["ticket"],
        max_items=2,
    )

    catalog = [
        CartItem(sku="TK-A", name="GA Standing", category="ticket", unit_price=240.0),
        CartItem(sku="TK-B", name="VIP Seated", category="ticket", unit_price=480.0),
        CartItem(sku="MR-X", name="Tour Hoodie", category="merch", unit_price=80.0),
    ]
    merchant = MerchantAgent.create(merchant_id="ticketz", catalog=catalog)

    # 想定通り 480 USD で 2 枚 → 上限内
    run("OK: GA 2 枚 (480 USD)", signed_intent, merchant, ["TK-A", "TK-A"])

    # 上限超過 (960 USD)
    run("NG: VIP 2 枚 (960 USD)", signed_intent, merchant, ["TK-B", "TK-B"])

    # 許可外カテゴリ混入
    run("NG: hoodie 混入", signed_intent, merchant, ["TK-A", "MR-X"])

    # 数量超過
    run("NG: 3 枚 (max_items=2)", signed_intent, merchant, ["TK-A", "TK-A", "TK-A"])


if __name__ == "__main__":
    main()
