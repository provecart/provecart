# CLAUDE.md

Follow `AGENTS.md` in this repo — it is the canonical instruction
file for all coding agents here. The three rules that matter most:

1. Never remove or bypass `check_cart_before_payment`; payment
   only follows a MATCH in the same run.
2. BLOCK → fix inside the customer's authorization and re-check
   with `previous_record_id`. REVIEW → ask the customer.
3. After changing prompts, models, or tools, the certification
   workflow must pass before the change ships.
