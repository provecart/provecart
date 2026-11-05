# {{ cookiecutter.agent_name }}

A shopping agent generated from the ProveCart Cookiecutter template.
It buys on a customer's behalf and checks its built cart against the
customer's instructions **before** payment — MATCH / REVIEW / BLOCK
via [ProveCart](https://provecart.com). The payment step refuses to
run unless the most recent check in the same run returned MATCH.

Provider: `{{ cookiecutter.provider }}`{% if cookiecutter.use_mcp %} · MCP companion: `mcp_agent.py` (raw MCP client that signs itself up and takes the live certification exam){% endif %}

## Run it — offline demo, no keys

```bash
pip install -r requirements.txt
python shopping_agent.py
```

The demo walks the whole loop against a local mock with the real
response shape: wrong-variant cart → BLOCK with a correction →
fix inside the customer's authorization → linked re-check → MATCH
→ payment gate opens.

## Go live

```bash
cp .env.example .env   # fill in your keys
export LIVE_MODE=true
```

Free integrator signup for a ProveCart key:
https://provecart.com/agents.md

## Keep the invariant

`AGENTS.md` / `CLAUDE.md` in this repo tell coding agents to keep
the check in front of payment. The certification workflow
(`.github/workflows/certify.yml`) re-runs the free ProveCart
Verified Agent exam on every release.

MIT licensed sample code. ProveCart is built in the Bay Area.
