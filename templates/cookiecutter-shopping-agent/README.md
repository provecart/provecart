# Cookiecutter template — ProveCart shopping agent

Generate a shopping agent that is born checking before payment:
built cart → ProveCart conformity check (MATCH / REVIEW / BLOCK)
→ payment only after MATCH, BLOCK fixes stay inside the customer's
authorization and re-check linked, REVIEW stops and asks.

## Use it (exact route, from the flagship repo)

```bash
pip install cookiecutter
cookiecutter gh:provecart/provecart --directory templates/cookiecutter-shopping-agent
```

You will be asked for:

| Variable | Meaning |
|---|---|
| `project_slug` | Folder / project name for the generated agent |
| `agent_name` | Display name for your agent |
| `provider` | `openai` or `anthropic` — sets the SDK requirement, the `.env.example` key, and the certification workflow provider |
| `use_mcp` | `True` also includes `mcp_agent.py`, the raw MCP client that signs itself up keylessly and takes the live certification exam; `False` omits it |

## Run the generated project — offline demo, no keys

```bash
cd <your project_slug>
pip install -r requirements.txt
python shopping_agent.py
```

Offline by default: the check routes to a local mock with the real
response shape, so the BLOCK → fix → MATCH → payment-gate loop runs
with no keys and no network. Set `LIVE_MODE=true` and
`PROVECART_API_KEY` (free signup: https://provecart.com/agents.md)
to call the real ProveCart API.

## What the generated project contains

- `shopping_agent.py` — the agent + the offline demo loop
- `provecart_client.py` — the ProveCart client and verdict routing
  (same proven file as the starter repos)
- `mcp_agent.py` — only when `use_mcp` is true
- `AGENTS.md` / `CLAUDE.md` — coding-agent invariants that keep the
  check in front of payment
- `.github/workflows/certify.yml` — ProveCart Verified Agent exam
  wired into release CI
- `README.md`, `requirements.txt`, `.env.example`, `.gitignore`,
  `LICENSE`

Prefer a ready-made repo instead? See the two GitHub template
starters linked from the flagship README's "Start from a template"
section. ProveCart is built in the Bay Area.
