"""x402 + Coinbase CDP を使った AP2 購買エンドツーエンドサンプル.

事前準備 (詳細は README を参照):
  1. CDP API Key を発行し .env に登録 (CDP_API_KEY_ID/CDP_API_KEY_SECRET/CDP_WALLET_SECRET)
     もしくは EVM_PRIVATE_KEY を .env に登録
  2. Base Sepolia の USDC を少量取得 (Coinbase CDP Faucet 推奨)
  3. examples.x402_server を別ターミナルで起動
       uv run uvicorn examples.x402_server:app --port 4021
  4. 本スクリプト実行
       uv run python -m examples.x402_purchase
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

from ap2.agent import MerchantAgent, UserAgent
from ap2.cdp_signer import CdpEvmAccount
from ap2.mandates import CartItem
from ap2.x402_payment import X402PaymentProcessor

load_dotenv()


def main() -> None:
    paywall_url = os.getenv(
        "MERCHANT_PAYWALL_URL", "http://localhost:4021/merchant/checkout"
    )

    # 1. AP2: ユーザーエージェントが Intent Mandate を発行
    user = UserAgent.create(user_id="user-cdp-demo")
    intent = user.issue_intent(
        description="Premium API access (1 call, $0.01)",
        max_amount=1.00,
        currency="USD",
        allowed_categories=["api"],
        max_items=1,
    )

    # 2. AP2: マーチャント側エージェントが Cart Mandate を生成
    merchant = MerchantAgent.create(
        merchant_id="ap2-x402-merchant",
        catalog=[
            CartItem(
                sku="API-CALL-001",
                name="Premium API call",
                category="api",
                unit_price=0.01,
            )
        ],
    )
    cart = merchant.propose_cart(intent, selected_skus=["API-CALL-001"])

    # 3. x402 サイナー (CDP 管理 EVM アカウント or ローカル鍵)
    account = CdpEvmAccount.from_env()
    print(f"Buyer EVM address: {account.address}")

    # 4. PaymentProcessor が Mandate 検証 + x402 経由でステーブルコイン送金
    processor = X402PaymentProcessor(account=account)
    receipt = processor.execute(intent, cart, merchant_paywall_url=paywall_url)

    print("\n=== AP2 + x402 Receipt ===")
    print(receipt)


if __name__ == "__main__":
    main()
