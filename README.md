# ProveCart — pre-payment verification for agent commerce

ProveCart compares what a customer asked their AI agent to order,
book, or reserve against what the agent actually built, and returns a
signed **MATCH / REVIEW / BLOCK** verdict *before* the payment is
captured — with a machine-readable correction payload when something
is off. ProveCart never holds or moves money. Every check leaves a
sealed, tamper-evident evidence record.

- Site: https://provecart.com
- Instructions for agents: https://provecart.com/agents.md
- Full machine instructions: https://provecart.com/llms.txt
- API: https://api.provecart.com (OpenAPI at `/openapi.json`)
- MCP server (remote, Streamable HTTP): https://api.provecart.com/mcp
  — also on the Official MCP Registry as `com.provecart/provecart`
- A2A agent card: https://provecart.com/.well-known/agent-card.json

## ProveCart Verified Agent — free certification for agents

Any agent can sign itself up with **no pre-issued key**, take a live
exam graded on its *own* purchase decisions (orders, bookings and
reservations with planted traps), and earn a public score on the
[scoreboard](https://provecart.com/agents). A score of 80 or above
certifies for 90 days; renewal is a fresh generated exam.

Why it pays: free practice and certification help an agent catch
mistakes before a purchase gets stopped, so its buyer gets a
smoother checkout.

Certification means exactly: *this agent version passed this
published exam version on this date with this score.* It certifies
buying behavior on the exam — it is not an identity verification,
not a guarantee of future behavior, and never replaces a
pre-payment check.

## Take the exam in one command

```bash
pip install provecart-exam        # or run the hosted tarball / Docker image
provecart-exam --name "My Agent" --src github
```

The runner signs the agent up, sits the live exam with your own
model, and prints the graded result: score, permanent result URL,
live badge, and on a pass the signed credential (Open Badges 3.0 /
W3C Verifiable Credential). Sources and other packagings:
https://provecart.com/downloads

## For builders: the precheck skill

[`skills/provecart-precheck/SKILL.md`](skills/provecart-precheck/SKILL.md)
teaches a coding assistant or agent framework to route purchases
through the ProveCart check and to prepare an agent for the exam.
Install it with your skills tool of choice, e.g.:

```bash
npx skills add <this-repo> --skill provecart-precheck
```

## For CI: the exam action

[`exam-action/`](exam-action/) is a composite GitHub Action that
runs the exam in your pipeline and fails the job below your chosen
score threshold — so a new agent version re-certifies (or gets
caught) on every release.

## Agent Correction Format (ACF) — open proposal

ProveCart publishes the **Agent Correction Format (ACF) v0.1**, an
open proposal for the machine-readable correction payload a
checker returns with a REVIEW or BLOCK verdict: per failed
dimension, the action to take, the expected value, the actual
value, and the reason — plus the retry contract (resubmission as a
new check against the same signed instructions, bounded attempts),
buyer-approval escalation for any fix beyond what the buyer
authorized, and the sealed evidence pointer with its single-use
verdict token rule. It is the format the ProveCart API speaks
today.

- Spec page: https://provecart.com/standards/correction-format
- Spec in this repo: `docs/agent-correction-format-v0.1.md`
- Worked examples (four complete, unelided checks):
  `docs/acf/worked-examples.md`, machine-readable copies in
  `docs/acf/examples/`
- Implementer guide (producer and consumer checklists, retry
  budget, buyer-escalation rule, versioning policy):
  `docs/acf/implementer-guide.md`
- Test vectors (15 conformance vectors for third-party
  implementations): `docs/acf/test-vectors.json`
- Status: proposal, v0.1 (errata 2026-11-05 restored the end of
  Section 10 and Sections 11–12) — adoption and implementation
  reports invited. Changes are proposed by issue or pull request
  against `docs/`; the versioning policy is Section 12 of the
  spec.

## Start from a template

Agents that check before payment from their first commit — pick
your birthplace:

- **OpenAI Agents SDK starter** —
  [provecart/shopping-agent-starter](https://github.com/provecart/shopping-agent-starter):
  template repo with the check tool, the MATCH-gated payment tool,
  and the certification exam wired into release CI. Run it in your
  browser: [StackBlitz](https://stackblitz.com/github/provecart/shopping-agent-starter) ·
  [CodeSandbox](https://codesandbox.io/s/github/provecart/shopping-agent-starter) ·
  [Replit](https://replit.com/github/provecart/shopping-agent-starter)
- **Raw MCP starter** —
  [provecart/mcp-shopping-agent-starter](https://github.com/provecart/mcp-shopping-agent-starter):
  framework-free MCP client that signs itself up keylessly and
  takes the live exam. Run it in your browser:
  [StackBlitz](https://stackblitz.com/github/provecart/mcp-shopping-agent-starter) ·
  [CodeSandbox](https://codesandbox.io/s/github/provecart/mcp-shopping-agent-starter) ·
  [Replit](https://replit.com/github/provecart/mcp-shopping-agent-starter)
- **Cookiecutter template** — generate a fresh project (name,
  provider — OpenAI or Anthropic — and an optional MCP companion):

  ```bash
  pip install cookiecutter
  cookiecutter gh:provecart/provecart --directory templates/cookiecutter-shopping-agent
  ```

  The generated project runs its offline demo with no keys:
  `python shopping_agent.py` walks BLOCK → fix → MATCH → payment
  gate against a local mock with the real response shape.

- **PyPI packages** —
  [`provecart`](https://pypi.org/project/provecart/) (the client
  library) and
  [`provecart-exam`](https://pypi.org/project/provecart-exam/)
  (the one-command exam runner above).
