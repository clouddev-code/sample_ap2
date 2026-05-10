"""マーチャント側の x402 paywall サーバー (FastAPI).

`uv run uvicorn examples.x402_server:app --port 4021` で起動.
`/merchant/checkout` は Base Sepolia 上の USDC 0.01 USD 相当の支払いを要求する.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from x402.http import FacilitatorConfig, HTTPFacilitatorClient, PaymentOption
from x402.http.middleware.fastapi import PaymentMiddlewareASGI
from x402.http.types import RouteConfig
from x402.mechanisms.evm.exact import ExactEvmServerScheme
from x402.schemas import Network
from x402.server import x402ResourceServer

load_dotenv()

EVM_NETWORK: Network = "eip155:84532"  # Base Sepolia
EVM_ADDRESS = os.getenv("MERCHANT_PAY_ADDRESS")
FACILITATOR_URL = os.getenv("X402_FACILITATOR_URL", "https://x402.org/facilitator")

if not EVM_ADDRESS:
    raise RuntimeError("MERCHANT_PAY_ADDRESS env var is required")

app = FastAPI(title="AP2 Sample Merchant")

facilitator = HTTPFacilitatorClient(FacilitatorConfig(url=FACILITATOR_URL))
server = x402ResourceServer(facilitator)
server.register(EVM_NETWORK, ExactEvmServerScheme())

routes = {
    "GET /merchant/checkout": RouteConfig(
        accepts=[
            PaymentOption(
                scheme="exact",
                pay_to=EVM_ADDRESS,
                price="$0.01",
                network=EVM_NETWORK,
            ),
        ],
        mime_type="application/json",
        description="AP2 sample checkout (USDC 0.01 USD on Base Sepolia)",
    ),
}
app.add_middleware(PaymentMiddlewareASGI, routes=routes, server=server)


@app.get("/merchant/checkout")
async def checkout(request: Request) -> dict:
    intent_id = request.headers.get("X-AP2-Intent-Id", "<unknown>")
    cart_id = request.headers.get("X-AP2-Cart-Id", "<unknown>")
    return {
        "status": "settled",
        "intent_mandate_id": intent_id,
        "cart_mandate_id": cart_id,
        "message": "Payment confirmed via x402 + AP2",
    }


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "network": EVM_NETWORK, "facilitator": FACILITATOR_URL}
