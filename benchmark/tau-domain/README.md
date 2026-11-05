# shopping_traps — a tau-bench-style domain pack

A small task domain in the style of τ-bench / τ²-bench, testing the
moment other domains take for granted: **the purchase decision
itself.** Each task gives an agent a customer's instruction and a
shelf with a planted trap — a wrong-brand twin at the same price, a
fit fact that lives only in listing prose, fees that push the total
over the customer's ceiling, a reservation under the wrong name —
and grades the one decision the agent submits.

## Contents

| File | What it is |
|---|---|
| `tasks.json` | 12 tasks: instruction, shelf, mandate, the trap (with the trap submission), and mechanically-gradeable expected outcome per task. |
| `policy.md` | The customer rules the agent is graded against (the domain policy document, in τ-bench style). |
| `tools.py` | The three-tool surface: `get_shelf`, `submit_decision`, `ask_customer`. |
| `grade.py` | The mechanical grader + self-test (correct decision → 1.0, trap → 0.0 on all 12 tasks). |

## How this maps to τ-bench, honestly

τ-bench tasks are multi-turn dialogues graded on final database
state. This pack keeps the τ-bench *shape* — a domain with a policy
document, a tool surface, tasks with `user_scenario` and
`evaluation_criteria`, and a reward that is computed, not judged —
and adapts the interaction to a **single decision**, because the
failure under test happens in one step: the agent builds a cart,
booking, or reservation that does not conform to the instruction
and pays for it. Grading is exact comparison of the submitted
decision against the task's expected safe decision (reward basis
`DECISION`), with one deliberate addition: on tasks whose
instruction is genuinely ambiguous, answering `ASK` — stopping to
ask the customer — earns the reward. Knowing when not to buy is
part of buying correctly.

The twelve tasks reuse the trap families of the public ProveCart
Verified Agent practice set (identity, fit, spec, budget, quantity,
merchant, terms, booking, reservation, ambiguity) — the same
families the live ProveCart exam generates fresh per session. This
pack is the fixed, published, offline form; nothing here is the
graded exam.

## Run the grader self-test

```sh
python3 grade.py
# shopping_traps_01: correct->1.0 trap->0.0
# ... (all 12) ...
# grader self-test: PASS
```

## Provenance

Published by ProveCart (pre-payment conformity checks for agent
orders, bookings, and reservations; Bay Area; patent pending) as a
standalone domain pack on its own ground:
`github.com/provecart/provecart` under `benchmark/tau-domain/`.
A staged proposal for the τ²-bench maintainers accompanies it in
the ProveCart working papers; this pack does not claim to be part
of τ-bench or endorsed by its authors.
