#!/usr/bin/env python3
"""Mock-mode example: no network, no keys. Default mode is mock."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from provecart_langgraph import provecart_check_node, provecart_route, guard_purchase_tool, FakeClient, ProveCartBlocked
from provecart_langgraph._core import match_response, block_fixable_response, review_response

CART = {"mandate_id": "m_demo", "merchant": {"name": "Example Store"},
        "items": [{"name": "Sony WH-1000XM5 headphones", "quantity": 1, "unit_price": 299.0}],
        "total_price": 299.0}

for label, resp in [("good cart", match_response()), ("fixable cart", block_fixable_response()), ("unclear cart", review_response())]:
    node = provecart_check_node(FakeClient(response=resp))
    update = node({"cart": CART})
    print(f"{label}: decision={update['provecart_decision']} route={provecart_route(update)} verdict={update['provecart_verdict']}")

paid = []
@guard_purchase_tool(client=FakeClient(response=block_fixable_response()))
def pay(cart):
    paid.append(cart); return "paid"
try:
    pay(CART)
except ProveCartBlocked as e:
    print(f"tool guard: payment blocked, corrections={e.corrections}, paid={paid}")
