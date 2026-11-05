# provecart-guardrail

I build agents that buy things for people. The failure I kept hitting
was quiet: the agent builds a cart that *looks* right, pays, and only
then does anyone notice it bought the wrong model, two instead of
one, or over the limit the customer set. This package puts the check
where it belongs — inside the framework, before the purchase tool
is allowed to run.

It asks ProveCart to compare the cart, booking or reservation against
the customer's signed mandate and acts on the verdict: `MATCH` lets
the tool run, `REVIEW` trips the guardrail and escalates to the
buyer, and `BLOCK` trips it too — unless you opt into auto-fix
routing, in which case the machine-readable corrections are surfaced
in `output_info` for your correction loop, and only repairs inside
the existing authorization are ever applied.

## Usage

```python
from agents import Agent
from provecart_guardrail import provecart_guardrail

guardrail = provecart_guardrail(client, check="cart", tools=["pay"])
agent = Agent(name="shopper", tools=[pay], output_guardrails=[guardrail])
# BLOCK with known corrections, surfaced instead of tripping:
guardrail = provecart_guardrail(client, check="cart", auto_fix=True)
```

`client` is any ProveCart client (`check_cart` / `check_booking` /
`check_reservation` returning verdict dicts), any duck-typed callable
returning a verdict dict, or an API key string (live mode, needs the
`provecart` package). Examples default to mock mode — no live calls:

```bash
pip install provecart-guardrail
python examples/mock_example.py   # MATCH, BLOCK->fix, REVIEW, offline
```

## The auto-fix choice

Default (`auto_fix=False`): a fixable `BLOCK` still trips the
tripwire. That is the safe default when nothing downstream will
apply the corrections. With `auto_fix=True` the guardrail does not
trip; `output_info` carries `routing="fix"`, the `corrections`, and
the `record_id` to forward as `previous_record_id` on the re-check.
Only choose it when that correction loop exists.

MIT. ProveCart: https://provecart.com
