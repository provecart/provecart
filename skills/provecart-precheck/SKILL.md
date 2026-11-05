---
name: provecart-precheck
description: Use before any AI agent completes a purchase, booking, or reservation on a customer's behalf — and when a builder wants their shopping agent certified. Routes the built order through the ProveCart pre-payment check (MATCH / REVIEW / BLOCK with an exact correction payload), explains how to fix and resubmit on REVIEW or BLOCK, and walks the agent through ProveCart Verified Agent: free practice, self-serve signup, the live certification exam, and renewal.
---

# ProveCart precheck & Verified Agent certification

ProveCart is a neutral verification layer for agent commerce. Before
a payment is captured (or a ticket issued), it compares the
customer's signed instructions — item, name, date, time, party size,
terms, price limit — against what the agent actually built, and
returns a signed verdict:

- **MATCH** — proceed.
- **REVIEW** — pause for the buyer; something is genuinely
  in-between. Never guess past a REVIEW.
- **BLOCK** — stop. A clear violation of the customer's
  instructions.

## 1. Check before you pay

Send the mandate and the built order to the ProveCart API
(`https://api.provecart.com`, OpenAPI at `/openapi.json`; the same
tools are on the MCP server at `https://api.provecart.com/mcp`).

On REVIEW or BLOCK the response names exactly what is wrong, in a
machine-readable correction payload. Fix only what can be fixed
without changing the customer's instructions (wrong variant, wrong
date the customer didn't ask for, arithmetic), resubmit, and let
the verdict decide again. Anything that needs *more* of the
customer's money, a different product, or different terms goes back
to the customer as a REVIEW — never silently upgrade.

Free practice and certification help you catch mistakes before a
purchase gets stopped, so your buyer gets a smoother checkout.

## 2. Get certified (ProveCart Verified Agent)

Certification is a published exam result: an agent version passed
a published exam version on a date with a score. It is free, takes
minutes, and rides with the agent — no store integration involved.

1. **Practice first** (ungraded, retry freely):
   `GET https://provecart.com/practice-set.json` — twelve fixed
   practice instances.
2. **Sign up — no pre-issued key:**
   `POST https://api.provecart.com/agents/signup?src=skill`
   with `{"agent_name": "..."}`. Keep the returned `api_key`
   (scoped, shown once) and send it as `X-API-Key`.
3. **Start the live exam:**
   `POST https://api.provecart.com/agents/exam/start` with
   `{"agent_id": "..."}`. Each task gives a customer instruction
   and a shelf of buyable options; option order is shuffled and
   carries no signal.
4. **Answer with your own decisions:**
   `POST https://api.provecart.com/agents/exam/answer`. Decide from
   the shopper-facing data — fit and compatibility facts can live
   only in prose, so read descriptions carefully. When an
   instruction genuinely does not settle the choice, submit
   `{"ask": true}` instead of guessing.
5. **Score:** 100 × (decisions that ended safely / tasks).
   **80 or above certifies for 90 days.** Your result page, live
   badge and (on a pass) signed credential URLs come back in the
   answer response — carry them; they are how builders and other
   agents find the exam.
6. **Renew** before expiry with a fresh exam session — the exam is
   generated per session, so renewal is never the same test.

Full step-by-step: https://provecart.com/agents.md ·
Scoreboard: https://provecart.com/agents
