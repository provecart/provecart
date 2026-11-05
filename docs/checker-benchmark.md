# Checker benchmark and audit fix log

ProveCart is a neutral verification service for agent commerce, based in the Bay Area, California. Before payment is captured — or, for travel, before a ticket is issued — ProveCart compares what an AI agent built against what the customer actually asked for, and answers MATCH, REVIEW, or BLOCK, with a correction the agent can act on and a sealed evidence record. This document publishes how accurate that checker is, how we measure it, where it is honestly limited, and every fix that came out of two independent external audits. Patent pending.

Published page: https://provecart.com/checker-benchmark

## How the benchmark works

We run trap batteries against our own engine. Each battery is a set of orders, bookings, and reservations whose correct verdict is known in advance, because each case was built that way: a conforming case should MATCH, a case with a planted mistake should be stopped (BLOCK) or escalated (REVIEW), and a good order should never be blocked. The batteries are re-run against the production engine build, and the results below are labeled by source: a local run on November 4, 2026, or the recorded production baseline from the same day.

The trap categories cover the mistakes agents actually make:

- **Item traps (orders):** the wrong item entirely, a near-miss product, an accessory offered in place of the product, a wrong brand — including a listing whose stated brand field contradicts its own product name — a required variant changed, a stated size or capacity that conflicts with the instructions, and extra items diluting the cart.
- **Money and merchant traps (orders):** a total over the customer's ceiling on either price basis, a stated total that disagrees with the computed total, too many items, the wrong currency, an expired instruction set, a blocked merchant, a merchant outside the allowed list, lookalike and subdomain merchants, and an allowlist entry matched only by a self-reported name.
- **Wording traps:** the right product described in different words — paraphrases, abbreviations, respelled units, and declared extras such as a warranty or gift wrap the customer approved. These should MATCH, or at worst REVIEW for a human decision, never BLOCK.
- **Booking traps:** a wrong traveler or a name that is a different person, wrong dates, a wrong city, a substituted airport inside the same metro area, too many or too-long connections, a cabin or fare-terms downgrade — for example a non-refundable fare where flexible was asked — and a total over the ceiling.
- **Reservation traps:** the wrong provider or branch, the wrong date, a time outside the agreed tolerance, a party that is too small or too large, a deposit or total over its limit, and cancellation terms weaker than the customer required.
- **AI-layer traps:** genuine mismatches written in friendly wording, submitted to see whether the AI review layer wrongly clears them; clear-cut BLOCK cases, to prove the AI layer never overturns a block; and provider-failure cases, to prove that when the AI layer is down, slow, or unsure, the rules verdict stands unchanged.

## Measured accuracy — local run, November 4, 2026

| Battery | Result | What it proves |
|---|---|---|
| Full endpoint and security battery (orders) | 60 of 60 checks passed | Core verdicts, capture gating, idempotency, tenant isolation, and every audit regression check named in the fix log below. |
| Labeled booking and reservation cases | 74 of 74 cases agreed (48 bookings, 26 reservations) | Every seeded booking and reservation trap was caught with the right verdict class. |
| Booking and reservation endpoint battery | 28 of 28 checks passed | Payment-capture and ticket-issuance gating, the correction loop, stale-verdict refusal, cross-type guards, and evidence-chain integrity across a restart. |
| AI-layer wording battery | 120 of 120 wording REVIEWs cleared, each with written reasoning | The live AI layer resolves the known wording class of false REVIEWs (see Known limits). |
| AI-layer adversarial battery | 0 wrongful clears out of 8 qualifying genuine mismatches | Friendly wording does not talk the AI layer into passing a real mismatch. |
| AI-layer BLOCK passthrough | 41 of 41 BLOCK cases still BLOCK, with no AI adjudication attached | The AI layer never runs on, and can never overturn, a BLOCK. |
| AI-layer failure modes | 52 of 52 cases identical to AI-off in each of three failure states; 8 of 8 identical under timeout | Provider down, provider error, or low confidence leaves the rules verdict standing. |
| AI intake battery | 54 of 54 extracted fields correct; 0 invented values | Free-text instructions are read into a draft without inventing fields the customer never stated. |
| Good-order stress spot-check | 20,000 good orders: 0 false BLOCKs; 97.65% MATCH; 2.35% false REVIEWs (470 orders) | Good orders are not blocked. The false REVIEWs are the wording class described under Known limits. |

Source: local run, November 4, 2026, against the current production engine build. The stress spot-check uses the same generator and seed as the recorded 100,000-order baseline below, bounded to 20,000 orders.

## Recorded production baseline — November 4, 2026

| Stress run | Result |
|---|---|
| 100,000 good orders (orders) | 0 false BLOCKs. 97.61% MATCH; false REVIEWs 2.39% (2,388 orders), every one in the single wording class described under Known limits. |
| 50,000 good bookings | 100% MATCH. 0 false BLOCKs, 0 false REVIEWs. |
| 50,000 good reservations | 100% MATCH. 0 false BLOCKs, 0 false REVIEWs. |

Source: recorded production baseline, November 4, 2026. "Good" means conforming by construction: each generated case satisfies its instructions, so any BLOCK is a false BLOCK and any REVIEW is a false REVIEW by definition.

The design rule behind these numbers: uncertainty goes to REVIEW, never to a silent MATCH, and only clear violations BLOCK. An engine error also returns REVIEW rather than guessing. That is why the false-BLOCK rate is the number we protect first, and why the remaining error shows up as extra human review on one wording class instead of refused purchases.

## Known limits, stated plainly

- **Facts stated only as prose grade REVIEW.** If a fit or compatibility fact — for example, that a spare part fits only one model — exists only as marketing text and not as structured data, the checker cannot prove conformity, so it escalates to REVIEW instead of passing the order silently. This is the honest verdict for that evidence, and it is why our catalog-readiness work matters alongside the check itself.
- **One wording class still produces false REVIEWs on the rules side.** In the good-order stress runs, every false REVIEW comes from a single shape: a product named with the word "bicycle" where the instructions say "bike," on carts that also carry customer-approved extras. The rules engine does not treat those two words as the same token, so the product line scores just short of a confident match. A rules-side synonym fix was deliberately not applied, because synonym changes affect every comparison and need their own evaluation pass. In production, the live AI layer — which runs only on REVIEWs of this wording class and can never overturn a BLOCK — clears these cases; the local AI-layer battery above cleared 120 of 120 sampled cases of this class.
- **Very short stays can segment ambiguously.** For bookings, an itinerary whose stay at the destination is under 24 hours, whose return departs inside the outbound departure window, and which also changes airport inside the same metro area can be genuinely ambiguous to split into outbound and return legs, and can be mis-split. The common shapes of this trap are covered by labeled cases in the battery; the fully ambiguous shape is a documented residual, not a silent pass.

## Audit fix log

On November 4, 2026, two independent external reviewers audited the checker — one by static review and testing, one by reproducing attacks against a running copy — and a third review later the same day probed the correction loop's retry link. Every finding below was reproduced, fixed, deployed to production, and verified with a named regression check. Severity is our plain-language rating of what the flaw could have done before the fix.

### The eleven-fix batch — November 4, 2026

1. **Tenant isolation not enforced** (High). One customer's key could read or verify against another customer's instruction sets. Fix: every instruction set is now bound to the key that created it; reading or verifying against another key's set returns the same sealed "not found" block as a missing set, so existence is not leaked. **FIXED — DEPLOYED, 2026-11-04.**
2. **Administration and signing shared one secret (code)** (High). The credential that administers keys was the same secret that signs instruction sets. Fix: the code now supports a separate, dedicated administration secret; signing never uses it. The code is deployed; switching production over to a dedicated secret value is a separate owner step, stated openly here rather than claimed as done. **FIXED — DEPLOYED, 2026-11-04.**
3. **Idempotency key was not bound to the request** (High). Reusing a retry key with a different cart replayed the old verdict. Fix: each retry key now stores a hash of the exact request; the same key with the same request replays the original response, and the same key with a different request is refused with a conflict response. **FIXED — DEPLOYED, 2026-11-04.**
4. **A stated size conflict passed as a match** (High). An item whose stated size contradicted the instructions could MATCH when the rest of the wording overlapped. Fix: a dedicated specification comparison now checks stated dimensions (length, weight, volume, capacity) on both sides; a conflict on a positively identified product BLOCKs, a conflict on an uncertain identification escalates to REVIEW — never a silent MATCH — and the AI layer is not permitted to clear this code. **FIXED — DEPLOYED, 2026-11-04.**
5. **Money bounds and stated totals** (High). Negative or unbounded amounts could defeat the price ceiling, and a stated total that disagreed with the computed total was not compared. Fix: negative amounts and quantities below one are now rejected at validation; when the stated and computed totals differ by more than a cent, the larger figure is compared against the ceiling and the discrepancy is sealed into the evidence record. **FIXED — DEPLOYED, 2026-11-04.**
6. **Non-finite numbers poisoned records** (High). "Not a number" and infinity values could be sealed as a match, break later reads, and break the shared verdict feed. Fix: non-finite numbers are rejected at validation on every request, including price ceilings; error responses and all record reads are also sanitized on the way out. **FIXED — DEPLOYED, 2026-11-04.**
7. **Behavior-watch poisoning could downgrade a block** (High). A poisoned baseline in the advisory behavior watcher could turn a later BLOCK into a REVIEW. Fix: the watcher can no longer raise an error into the verdict path, non-finite totals never enter its baselines, and the post-verdict components are isolated one by one — once a verdict is computed, a failure after it can never downgrade it. **FIXED — DEPLOYED, 2026-11-04.**
8. **Verdict tokens were reusable in the demonstration payment and ticketing flows** (Medium). One verdict could fund more than one capture, and a token was not checked against the hold it was presented with. Fix: each verdict record can now fund at most one capture or ticket issuance, and the token's instruction set and cart must match the hold's own stored values; the same rule is written into our integration specification as a requirement for real payment and ticketing integrations. These flows are demonstrations by design; no real payment or airline integration exists yet. **FIXED — DEPLOYED, 2026-11-04.**
9. **Record reads were not scoped to their owner** (High). Evidence records, outcomes, exports, and the verdict feed could be read across customers. Fix: every sealed record is stamped with the key that submitted it; reads return "not found" for non-owners, and the verdict feed returns only the caller's own records. **FIXED — DEPLOYED, 2026-11-04.**
10. **Intake confirmations were not linked to a real draft** (Medium). A hand-written draft with no sealed reader output behind it could be signed as if the AI reader had produced it. Fix: confirmation now requires the sealed draft record it belongs to — same customer, same kind, and not a failed attempt — and the confirmation record seals the field-by-field difference between the draft and what was confirmed; failed draft attempts are sealed too. **FIXED — DEPLOYED, 2026-11-04.**
11. **Merchant allowlist could be matched by a self-reported name** (Medium). A cart whose merchant name copied an allowed domain, while its actual domain was elsewhere, passed the merchant check. Fix: a domain-shaped list entry now matches on the merchant's domain only; a self-reported name can no longer satisfy it. **FIXED — DEPLOYED, 2026-11-04.**

### Correction-loop retry link — November 4, 2026

12. **The retry link was unvalidated** (High). A corrected resubmission points at the record it corrects; that pointer was copied into the new record unchecked, and standing-budget accounting trusted it globally — so a sacrificial resubmission could erase a real purchase from a standing budget, even across customers, and a superseded verdict stayed spendable. The bypass was reproduced before the fix. Fix: the link is now validated at intake — it must reference an existing verification record, under the same instruction set and the same key, still at the head of its attempt chain, and within the chain's retry budget. A missing or foreign reference is refused as a sealed BLOCK with no link recorded; a wrong-instruction-set, already-superseded, or over-budget link is refused outright. Standing-budget accounting is chain-aware — spend displaced only by a later matching attempt in its own chain stops counting, captured spend always counts — and a superseded verdict can no longer be captured or issued against. **FIXED — DEPLOYED, 2026-11-04.**

What the audits also left open, we say openly: a durable, database-backed evidence store is scheduled as a follow-on batch, and the question of how a customer's approval of their own instructions is anchored outside our store is an acknowledged design item on our roadmap. Neither is claimed as fixed here.

## Reproduce it

Outside reviewers are invited to re-run their cases against the current production build. If a number here does not reproduce, we would rather be told than believed. Questions: hello@provecart.com.
