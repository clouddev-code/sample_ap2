# sample_ap2 — Agent Payments Protocol (AP2) × x402 × Coinbase CDP

Google Cloud が公開した [Agent Payments Protocol (AP2)](https://cloud.google.com/blog/products/ai-machine-learning/announcing-agents-to-payments-ap2-protocol?hl=en) の中核アイデア (Mandate ベースの委任 / VC 署名 / 検証チェーン) を Python で再現し、**x402 (HTTP 402 Payment Required) プロトコル**経由で **Coinbase Developer Platform (CDP)** が管理する EVM ウォレットからステーブルコインで実決済する最小サンプル.

## アーキテクチャ概要

```
┌─────────────────┐     ┌────────────────────┐     ┌────────────────────┐
│ User Agent      │     │ Merchant Agent     │     │ x402 Resource Srv  │
│ (Ed25519)       │     │ (Ed25519)          │     │ (FastAPI paywall)  │
└────────┬────────┘     └─────────┬──────────┘     └─────────┬──────────┘
         │ Intent Mandate         │ Cart Mandate              │
         └────────────┬───────────┴───────────────────────────┘
                      ▼
            ┌──────────────────────────┐         ┌─────────────────────┐
            │ X402PaymentProcessor     │ ──────▶ │  x402 Facilitator   │
            │ - Mandate チェーン検証    │  HTTP   │  (Base Sepolia)     │
            │ - x402 で USDC 送金       │         │  https://x402.org/. │
            │ - 署名は CDP EVM Account │         └─────────────────────┘
            └──────────────────────────┘
```

| レイヤー | 役割 | 実装 |
|---------|------|------|
| **AP2 Mandate** | ユーザーが何をエージェントに許可したか | `ap2/mandates.py` (Ed25519 / W3C VC 風) |
| **AP2 検証**    | Cart が Intent の制約を満たすか | `ap2/validation.py` |
| **x402 決済**   | ステーブルコインの実送金 | `ap2/x402_payment.py` |
| **CDP 署名**    | 秘密鍵を出さずに EVM 署名 | `ap2/cdp_signer.py` |

> **AP2 と x402 はレイヤーが違う**:
> AP2 = "誰が何を許可したか" の証跡 (Verifiable Credentials)
> x402 = "実際にいくら誰に送金するか" の HTTP プロトコル

## ディレクトリ構成

```
sample_ap2/
├── pyproject.toml             # uv で管理
├── .env.example               # 環境変数テンプレ
├── ap2/
│   ├── crypto.py              # Ed25519 署名 / 検証 / canonical JSON
│   ├── mandates.py            # IntentMandate / CartMandate / SignedMandate
│   ├── validation.py          # Cart vs Intent の制約検証 (TODO(human) あり)
│   ├── agent.py               # UserAgent / MerchantAgent
│   ├── payment.py             # PaymentProcessor (モック)
│   ├── cdp_signer.py          # Coinbase CDP × x402 のサイナー連携
│   └── x402_payment.py        # AP2 検証 + x402 経由の実決済 PaymentProcessor
├── examples/
│   ├── realtime_purchase.py   # オフライン (モック決済) フロー
│   ├── delegated_task.py      # 委任タスク (モック) フロー
│   ├── x402_server.py         # FastAPI x402 paywall (マーチャント役)
│   └── x402_purchase.py       # AP2 + x402 + CDP のエンドツーエンド購買
└── tests/
    └── test_mandates.py       # ユニットテスト (オフライン)
```

## 主な依存関係

| パッケージ | 用途 |
|-----------|------|
| `cryptography` | Ed25519 鍵生成・Mandate 署名 |
| `x402[requests,fastapi,evm,extensions]` | x402 クライアント / サーバー / EVM スキーム |
| `cdp-sdk` | Coinbase CDP 管理ウォレット |
| `eth-account` | EVM 署名 (CDP 不使用時) |
| `python-dotenv` | `.env` ロード |
| `fastapi` / `uvicorn` | マーチャント側 paywall サーバー |
| `pytest` (dev) | テスト |

## セットアップ手順

### 1. 依存関係インストール

```bash
cd /Users/hiruta/work/sample_ap2
uv sync
```

### 2. 環境変数の用意

```bash
cp .env.example .env
```

#### CDP モード (推奨)

[Coinbase Developer Platform](https://portal.cdp.coinbase.com/) で API Key を発行し `.env` に貼り付ける:

```env
CDP_API_KEY_ID=your-key-id
CDP_API_KEY_SECRET=your-key-secret
CDP_WALLET_SECRET=your-wallet-secret
CDP_ACCOUNT_NAME=ap2-buyer
```

最初の実行時に `ap2-buyer` という名前の EVM アカウントが CDP 上に作られる.
**秘密鍵はローカルに出ない** — CDP がカストディアル管理する.

#### ローカル鍵モード (CDP を使わない場合)

```env
EVM_PRIVATE_KEY=0xabc123...
```

`EVM_PRIVATE_KEY` が設定されていれば自動でこちらが優先される.

### 3. テストネット USDC を入手

Buyer のアドレスを表示:

```bash
uv run python -c "from ap2.cdp_signer import CdpEvmAccount; print(CdpEvmAccount.from_env().address)"
```

[Coinbase CDP Faucet](https://portal.cdp.coinbase.com/products/faucet) で **Base Sepolia の USDC** を上記アドレスに送る.

### 4. マーチャント受取アドレスを設定

`.env` の `MERCHANT_PAY_ADDRESS` に任意の Base Sepolia EVM アドレスを設定する (動作確認用に上記 buyer と同じアドレスでも可).

---

## 動作検証手順

### Step 1: ユニットテスト (オフライン)

```bash
uv run pytest -v
```

✅ **期待**: 全テストが PASS
❌ 失敗時: `ap2/validation.py` の `TODO(human)` が未実装の可能性が高い

### Step 2: モック決済フロー (オフライン)

```bash
uv run python -m examples.realtime_purchase
uv run python -m examples.delegated_task
```

✅ **期待**:
- `realtime_purchase`: `status=SUCCESS, amount=149.0`
- `delegated_task`: 4 シナリオ (1 件 SUCCESS, 3 件 FAILED)

### Step 3: x402 paywall サーバー起動 (ターミナル A)

```bash
uv run uvicorn examples.x402_server:app --port 4021
```

✅ **期待**: ヘルスチェック `curl localhost:4021/health` で `{"ok":true,"network":"eip155:84532",...}` が返る

### Step 4: AP2 + x402 + CDP エンドツーエンド (ターミナル B)

```bash
uv run python -m examples.x402_purchase
```

✅ **期待出力例**:
```
Buyer EVM address: 0x...
=== AP2 + x402 Receipt ===
PaymentReceipt(payment_id='pay_...', status='SUCCESS',
               amount=0.01, currency='USD',
               reason='x402 ok | tx_header=...')
```

#### 内部で起こっていること
1. `UserAgent` が **Intent Mandate** を Ed25519 署名
2. `MerchantAgent` が **Cart Mandate** を Ed25519 署名
3. `X402PaymentProcessor` が両 Mandate を検証 (`validate_cart_against_intent`)
4. `x402_requests` セッションが `/merchant/checkout` に GET → 402 を受領
5. CDP 管理 EVM アカウントが EIP-3009 `transferWithAuthorization` に署名
6. x402 クライアントが署名を `X-PAYMENT` ヘッダに乗せて再リクエスト
7. FastAPI ミドルウェアが facilitator (`x402.org`) で検証 / settle
8. Base Sepolia 上で USDC 0.01 が `MERCHANT_PAY_ADDRESS` に送金
9. 200 応答とともに settlement TxHash がレスポンスヘッダに入る

### Step 5: 失敗ケースの確認

`.env` の `MERCHANT_PAY_ADDRESS` を別 EVM アドレスに変更したり、
`UserAgent.issue_intent` の `max_amount` を `0.005` に下げたりして
`AP2 Mandate validation failed` で 402 にすら到達しないことを確認.

---

## 実装上の重要な選択

### Ed25519 を Mandate 署名に採用
- W3C Verifiable Credentials の標準曲線
- 鍵が短く高速 (32B 公開鍵 / 64B 署名)
- 決定論的署名で nonce 由来の事故が起きない

### x402 と AP2 を分離
- AP2 Mandate (Ed25519, ユーザー身元) と x402 (EIP-3009, EVM 署名) は**目的が違う**ので別レイヤーに保つ
- `X402PaymentProcessor` が両者をブリッジ (Mandate 検証 OK → x402 決済へ)

### CDP × x402 ブリッジは `EvmLocalAccount`
- CDP の `EvmServerAccount` を `cdp.evm_local_account.EvmLocalAccount` でラップ
- これで `eth_account.LocalAccount` 互換になり、x402 の `EthAccountSigner()` にそのまま渡せる
- **秘密鍵がローカルに出ない**ためエージェントが盗まれても被害が限定的

### Base Sepolia + x402.org facilitator
- テストネットは無料・無認証で動作確認できる
- 本番は CDP の認証付き facilitator (`https://api.cdp.coinbase.com/platform/v2/x402`) に切り替え

---

## AP2 仕様との対応表

| AP2 概念 | 本サンプル実装 |
|---------|---------------|
| Verifiable Credential | `SignedMandate` (`payload + signature + issuer_public_key`) |
| Intent Mandate | `IntentMandate` |
| Cart Mandate | `CartMandate` (`intent_mandate_id` で連鎖) |
| User Agent | `UserAgent.issue_intent()` |
| Merchant Agent | `MerchantAgent.propose_cart()` |
| Authorization 検証 | `validate_cart_against_intent()` |
| Payment Method (x402) | `X402PaymentProcessor.execute()` |

---

## 拡張アイデア

- **Solana mainnet**: `register_exact_svm_client` + `KeypairSigner` で SPL Token 決済
- **CDP 認証付き facilitator**: `FacilitatorConfig(url="https://api.cdp.coinbase.com/platform/v2/x402", auth_provider=...)` を追加
- **失効リスト (Status List 2021)**: ユーザーが Intent Mandate を失効できるエンドポイント
- **マルチエージェント協調**: 1 つの Intent から複数 Cart を派生させ、合算金額を制約に
