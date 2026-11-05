# provecart-langgraph

My LangGraph agents kept paying first and explaining later. The
graph would build a cart, call the payment node, and the first
signal that the order was wrong — wrong item, wrong quantity, over
the customer's limit — was a return. This package moves the check
into the graph: a node that runs before payment, and a guard for
purchase tools, both driven by the same ProveCart verdict.

ProveCart compares the cart, booking or reservation against the
customer's signed mandate. `MATCH` proceeds to payment. `BLOCK`
returns machine-readable corrections and routes to your fix node —
apply only repairs inside the existing authorization, then re-check.
`REVIEW` routes to escalation and a human decides. Nothing guesses,
and nothing widens what the customer authorized.

## Usage

```python
from langgraph.graph import StateGraph, START, END
from provecart_langgraph import provecart_check_node, provecart_route

g = StateGraph(dict)
g.add_node("check", provecart_check_node(client, check="cart"))
g.add_node("pay", pay_node); g.add_node("fix", fix_node); g.add_node("ask", ask_node)
g.add_edge(START, "check")
g.add_conditional_edges("check", provecart_route,
    {"proceed": "pay", "fix": "fix", "escalate": "ask"})
```

```bash
pip install provecart-langgraph
python examples/mock_example.py   # mock mode, offline, no keys
```

There is also a tool guard for graphs that pay through a tool:
`guard_purchase_tool(pay_fn, client)` wraps the callable so the
check runs first and the tool body never executes on `BLOCK` or
`REVIEW`. `client` is any ProveCart client, any duck-typed callable
returning a verdict dict, or an API key string (live mode, needs
the `provecart` package). Examples default to mock mode.

MIT. ProveCart: https://provecart.com
