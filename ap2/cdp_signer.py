"""Coinbase CDP × x402 のサイナー連携.

CDP がサーバーサイドで管理する EVM アカウントを `EvmLocalAccount` でラップし、
`eth_account.LocalAccount` 互換にしてから x402 の `EthAccountSigner` に渡す.
これにより秘密鍵をローカルに置かずに x402 決済の署名ができる.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from cdp import CdpClient
from cdp.evm_local_account import EvmLocalAccount
from eth_account import Account
from x402.mechanisms.evm import EthAccountSigner


@dataclass
class CdpEvmAccount:
    """CDP / ローカル両対応のアカウント抽象."""

    address: str
    signer: EthAccountSigner

    @classmethod
    async def from_cdp(cls, account_name: str = "ap2-buyer") -> "CdpEvmAccount":
        """CDP_API_KEY_ID / CDP_API_KEY_SECRET / CDP_WALLET_SECRET を環境変数から読み、
        指定名のアカウントを取得 (なければ作成) してサイナーを返す."""
        async with CdpClient() as cdp:
            account = await cdp.evm.get_or_create_account(name=account_name)
            local = EvmLocalAccount(account)
        return cls(address=local.address, signer=EthAccountSigner(local))

    @classmethod
    def from_private_key(cls, private_key_hex: str) -> "CdpEvmAccount":
        """ローカル秘密鍵モード (CDP を使わない場合のフォールバック)."""
        local = Account.from_key(private_key_hex)
        return cls(address=local.address, signer=EthAccountSigner(local))

    @classmethod
    def from_env(cls) -> "CdpEvmAccount":
        """環境変数を見て CDP / ローカル鍵のどちらかを自動選択する.

        優先順位:
          1. EVM_PRIVATE_KEY が設定されていればローカル鍵モード
          2. それ以外は CDP モード (要 CDP_API_KEY_ID/SECRET, CDP_WALLET_SECRET)
        """
        pk = os.getenv("EVM_PRIVATE_KEY")
        if pk:
            return cls.from_private_key(pk)
        # CDP モードは非同期初期化が必要
        import asyncio

        return asyncio.run(cls.from_cdp(os.getenv("CDP_ACCOUNT_NAME", "ap2-buyer")))
