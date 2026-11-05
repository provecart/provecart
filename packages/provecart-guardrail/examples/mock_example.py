#!/usr/bin/env python3
"""Mock-mode example: no network, no keys. Default mode is mock."""
import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from provecart_guardrail import provecart_guardrail, FakeClient
from provecart_guardrail._core import match_response, block_fixable_response, review_response

async def main():
    cart = {"mandate_id": "m_demo", "merchant": {"name": "Example Store"},
            "items": [{"name": "Sony WH-1000XM5 headphones", "quantity": 1, "unit_price": 299.0}],
            "total_price": 299.0}
    for label, resp in [("good cart", match_response()),
                        ("fixable cart", block_fixable_response()),
                        ("unclear cart", review_response())]:
        g = provecart_guardrail(FakeClient(response=resp), check="cart")
        out = await g(None, None, {"tool_name": "pay", "arguments": cart})
        print(f"{label}: tripwire={out.tripwire_triggered} info={out.output_info}")
    g = provecart_guardrail(FakeClient(response=block_fixable_response()), auto_fix=True)
    out = await g(None, None, cart)
    print(f"fixable + auto_fix=True: tripwire={out.tripwire_triggered} routing={out.output_info.get('routing')} corrections={out.output_info.get('corrections')}")

if __name__ == "__main__":
    asyncio.run(main())
