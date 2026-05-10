"""Ed25519 ベースの署名・検証ユーティリティ.

AP2 の Mandate は Verifiable Credentials として暗号学的に署名される.
本サンプルでは Ed25519 を採用 (W3C VC でも標準, 鍵が短く高速).
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PrivateFormat,
    PublicFormat,
    NoEncryption,
)


def canonical_json(payload: dict[str, Any]) -> bytes:
    """署名対象を決定論的に直列化する.

    キー順序や空白で署名値が変わらないよう sort_keys と最小セパレータを使用.
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True)
class KeyPair:
    """Ed25519 鍵ペア (発行者用)."""

    private_key: Ed25519PrivateKey
    public_key: Ed25519PublicKey

    @classmethod
    def generate(cls) -> "KeyPair":
        sk = Ed25519PrivateKey.generate()
        return cls(private_key=sk, public_key=sk.public_key())

    def public_key_b64(self) -> str:
        raw = self.public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
        return base64.b64encode(raw).decode("ascii")

    def private_key_pem(self) -> bytes:
        return self.private_key.private_bytes(
            Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
        )


def sign_payload(payload: dict[str, Any], keypair: KeyPair) -> str:
    """Mandate ペイロードに署名し base64 文字列を返す."""
    signature = keypair.private_key.sign(canonical_json(payload))
    return base64.b64encode(signature).decode("ascii")


def verify_signature(
    payload: dict[str, Any], signature_b64: str, public_key_b64: str
) -> bool:
    """署名検証. 失敗時は False を返す (例外は投げない)."""
    try:
        signature = base64.b64decode(signature_b64)
        raw_pub = base64.b64decode(public_key_b64)
        pub = Ed25519PublicKey.from_public_bytes(raw_pub)
        pub.verify(signature, canonical_json(payload))
        return True
    except (InvalidSignature, ValueError):
        return False
