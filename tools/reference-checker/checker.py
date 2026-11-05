#!/usr/bin/env python3
"""
Standalone reference checker for the Agent Correction Format (ACF) v0.2.

An independent, dependency-free implementation of the published format
(https://provecart.com/standards/correction-format,
schema: https://provecart.com/standards/acf-v0.2.schema.json), written
from the specification document, the JSON Schema and the conformance
fixtures alone. It talks to no service: you give it a buyer's signed
instruction (a mandate-shaped JSON document) and a built checkout
subject (cart, booking or reservation JSON), and it emits the v0.2
checkout fragment — the host's `messages[]` entries carrying
`com.provecart.conformity.*` codes, plus the single namespaced
conformity object — exactly as the spec defines them.

    python3 checker.py INSTRUCTION.json SUBJECT.json [--kind cart]
    python3 checker.py decide FRAGMENT.json

What this proves: the format is implementable from the document
alone, by code that shares nothing with the reference service. What
it does not do: hold evidence, issue verdict tokens, or authorize
anything. Its record ids and digests are deterministic functions of
its two inputs (that is what makes its output reproducible and its
idempotency anchor demonstrable offline); a production checker seals
records in its own evidence store and issues single-use, hold-bound
verdict tokens when a verdict is presented to authorize a downstream
action. This checker emits no `verdict_token` and no `evidence_url`,
and its output MUST NOT be presented as a payment authorization.

Author: ProveCart (reference code for the format it publishes).
License for this file: same terms as the spec package — free to
copy, share and implement, with attribution. The format itself is
royalty-free to implement (RAND-Z essential-claims commitment,
spec Section 16).

Implementation notes (the choices this implementation makes where
the spec leaves the comparison itself to the checker — the spec
defines the *reporting shape*, not the comparison):

* Dimension order follows the reference fixture captures: mandate
  signature, mandate expiry, merchant, then the subject dimensions.
* Item conformity uses a keyword-coverage rule over the mandate's
  `item_keywords` (falling back to the tokens of
  `item_description`): full coverage passes; partial coverage is
  indeterminate and routes to REVIEW (`item_indeterminate`); zero
  coverage is a positively identified different item
  (`item_mismatch`). A checker with catalog access should do
  better; the rule here is deliberately the weakest one that is
  still honest, and it is enough to reproduce every fixture.
* A merchant that is blocklisted, or absent from a non-empty
  allowlist, is `merchant_excluded` and non-correctable (spec
  Section 5.5): no edit of the checkout repairs it.
* Airport substitution is never silent: a leg endpoint that differs
  from the mandated airport fails with action `change_airport`
  (the code vocabulary has no airport-specific code; the failure
  is reported under `item_mismatch`, the itinerary being the
  booking's "item"). Provider/location failures on reservations
  follow the same rule with `change_provider` / `change_location`.
* `content` strings are this implementation's own renderings of
  the structured values (the spec requires the structured fields
  to govern); two sentences intentionally follow the shapes the
  published worked examples use (booking date, reservation time),
  because those examples are part of the published document.
* Signature verification: if the instruction carries a `signature`
  field and `--secret` is given, the checker verifies HMAC-SHA256
  over the canonical instruction (signature field excluded). With
  no secret it does not guess: the dimension is skipped and the
  omission is the caller's deployment choice, stated here.
* Standing-budget accounting needs the check history and is out
  of scope for an offline checker; everything else in the initial
  code vocabulary that a single instruction/subject pair decides
  is implemented.
"""
import hashlib
import hmac
import json
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone

NS = "com.provecart.conformity"
DEFAULT_TTL_MINUTES = 15
DEFAULT_MAX_ATTEMPTS = 3

KNOWN_CODES = {
    "price_over_ceiling", "price_below_floor", "quantity_over_max",
    "quantity_below_min", "item_mismatch", "item_indeterminate",
    "item_excluded", "variant_mismatch", "currency_mismatch",
    "merchant_excluded", "date_mismatch", "date_outside_window",
    "time_outside_tolerance", "party_size_mismatch", "name_mismatch",
    "cabin_mismatch", "fare_terms_mismatch", "deposit_over_limit",
    "cancellation_terms_mismatch", "mandate_expired",
    "mandate_signature_invalid", "standing_budget_exceeded",
    "engine_error",
}

KNOWN_ACTIONS = {
    "remove_item", "replace_item", "change_variant", "reduce_quantity",
    "reduce_total", "change_currency", "correct_traveler_name",
    "change_airport", "change_travel_date", "change_departure_time",
    "add_itinerary", "rebuild_itinerary", "change_cabin",
    "change_fare_terms", "add_hotel_stay", "change_room",
    "change_provider", "change_location", "change_date", "change_time",
    "change_party_size", "correct_reservation_name", "reduce_deposit",
    "change_cancellation_terms",
}

# JSONPointer targets per dimension, mirroring the pointer rules
# published with the spec package (validate_fixtures.py): the paths
# address the reference subject shapes; a host checkout addresses
# the equivalent field of its own shape by the same rule.
POINTER_BY_DIMENSION = {
    ("cart", "price"): "/total_price",
    ("cart", "quantity"): "/items",
    ("cart", "variant"): "/items/0/variant",
    ("cart", "currency"): "/currency",
    ("booking", "price"): "/price/total",
    ("booking", "currency"): "/currency",
    ("reservation", "price"): "/total_amount",
    ("reservation", "reservation_time"): "/time",
    ("reservation", "reservation_date"): "/date",
    ("reservation", "party_size"): "/party_size",
    ("reservation", "provider"): "/provider_name",
    ("reservation", "reservation_name"): "/name_on_reservation",
    ("reservation", "deposit"): "/deposit_amount",
    ("reservation", "cancellation_terms"): "/cancellation_terms",
    ("booking", "travelers"): "/travelers",
    ("booking", "cabin"): "/fare/cabin",
}
POINTER_BY_FIELD = {
    "departure_date": "/legs/0/depart_at",
    "time": "/time",
    "date": "/date",
}


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def digest_of(obj):
    return "sha256:" + hashlib.sha256(
        canonical(obj).encode("utf-8")).hexdigest()


def to_jsonpath(pointer):
    out = "$"
    for part in pointer.split("/"):
        if not part:
            continue
        out += f"[{part}]" if part.isdigit() else f".{part}"
    return out


def parse_ts(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def fmt_ts(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def tokens(text):
    return set(re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*",
                          (text or "").lower()))


def norm_name(text):
    return " ".join((text or "").lower().split())


class Result:
    """One per-dimension outcome, pre-projection."""

    def __init__(self, dimension, code, status, content, *,
                 action=None, expected=None, actual=None, field=None,
                 correctable=True, pointer=None, buyer_approval=False):
        self.dimension = dimension
        self.code = code            # bare failure code (no namespace)
        self.status = status        # "hard_fail" | "soft_fail"
        self.content = content
        self.action = action
        self.expected = expected
        self.actual = actual
        self.field = field
        self.correctable = correctable
        self.pointer = pointer      # explicit JSONPointer override
        # True when the only repair would change what the buyer
        # authorized (spec Section 8): the message then carries
        # requires_buyer_approval and severity requires_buyer_review
        # in any case, and the failure alone routes to REVIEW.
        self.buyer_approval = buyer_approval


# ------------------------------------------------------------------
# Shared dimensions
# ------------------------------------------------------------------

def check_signature(instruction, secret):
    sig = instruction.get("signature")
    if not sig or not secret:
        return None  # nothing verifiable offline; see module notes
    body = {k: v for k, v in instruction.items() if k != "signature"}
    want = hmac.new(secret.encode(), canonical(body).encode(),
                    hashlib.sha256).hexdigest()
    if hmac.compare_digest(want, str(sig)):
        return None
    return Result("mandate_signature", "mandate_signature_invalid",
                  "hard_fail",
                  "instruction signature does not verify",
                  correctable=False)


def check_expiry(instruction, now):
    exp = instruction.get("expires_at")
    if exp and parse_ts(exp) <= now:
        return Result("mandate_expiry", "mandate_expired", "hard_fail",
                      f"instruction expired at {exp}",
                      correctable=False)
    return None


def check_merchant(instruction, subject):
    merchant = subject.get("merchant") or {}
    domain = (merchant.get("domain") or "").lower()
    name = merchant.get("name") or domain
    blocklist = [d.lower() for d in instruction.get("merchant_blocklist")
                 or []]
    allowlist = [d.lower() for d in instruction.get("merchant_allowlist")
                 or []]
    if domain and domain in blocklist:
        return Result("merchant", "merchant_excluded", "hard_fail",
                      f"merchant '{name}' ({domain}) is on the "
                      f"mandate blocklist", correctable=False)
    if allowlist and domain not in allowlist:
        return Result("merchant", "merchant_excluded", "hard_fail",
                      f"merchant '{name}' ({domain}) is not on the "
                      f"mandate allowlist", correctable=False)
    return None


def money(value):
    return float(value) if value is not None else None


# ------------------------------------------------------------------
# Cart
# ------------------------------------------------------------------

def cart_results(instruction, subject):
    out = []
    items = subject.get("items") or []

    ceiling = money(instruction.get("max_total_price"))
    floor = money(instruction.get("min_total_price"))
    if subject.get("total_price") is not None:
        total = money(subject["total_price"])
    else:
        total = sum(money(i.get("unit_price")) * i.get("quantity", 1)
                    for i in items)
    if ceiling is not None and total is not None and total > ceiling:
        out.append(Result(
            "price", "price_over_ceiling", "hard_fail",
            f"total {total} exceeds the instruction ceiling "
            f"{ceiling} {instruction.get('currency', '')}".strip(),
            action="reduce_total", expected=ceiling, actual=total))
    elif floor is not None and total is not None and total < floor:
        out.append(Result(
            "price", "price_below_floor", "hard_fail",
            f"total {total} is below the instruction floor {floor}",
            expected=floor, actual=total, buyer_approval=True))

    cur = instruction.get("currency")
    if cur and subject.get("currency") and subject["currency"] != cur:
        out.append(Result(
            "currency", "currency_mismatch", "hard_fail",
            f"currency {subject['currency']} differs from mandated "
            f"{cur}", action="change_currency", expected=cur,
            actual=subject["currency"]))

    qty = sum(i.get("quantity", 1) for i in items)
    max_q = instruction.get("max_quantity")
    min_q = instruction.get("min_quantity")
    if max_q is not None and qty > max_q:
        out.append(Result(
            "quantity", "quantity_over_max", "soft_fail",
            f"total quantity {qty} exceeds mandate max_quantity "
            f"{max_q}", action="reduce_quantity", expected=max_q,
            actual=qty))
    elif min_q is not None and qty < min_q:
        out.append(Result(
            "quantity", "quantity_below_min", "soft_fail",
            f"total quantity {qty} is below mandate min_quantity "
            f"{min_q}", expected=min_q, actual=qty,
            buyer_approval=True))

    keywords = instruction.get("item_keywords") or \
        sorted(tokens(instruction.get("item_description")))
    description = instruction.get("item_description")
    excluded = [tokens(e) for e in instruction.get("excluded_items")
                or []]
    for idx, item in enumerate(items):
        name = item.get("name") or ""
        item_tokens = tokens(name)
        if any(ex and ex <= item_tokens for ex in excluded):
            out.append(Result(
                "item_match", "item_excluded", "hard_fail",
                f"item is excluded by the instruction: {name}",
                action="remove_item", expected=description,
                actual=name,
                pointer=f"/items/{idx}/name"))
            break
        if keywords:
            coverage = len(set(keywords) & item_tokens) / len(keywords)
            if coverage == 0:
                out.append(Result(
                    "item_match", "item_mismatch", "hard_fail",
                    f"item is not the instructed item: {name}",
                    action="replace_item", expected=description,
                    actual=name, pointer=f"/items/{idx}/name"))
                break
            if coverage < 1:
                out.append(Result(
                    "item_match", "item_indeterminate", "soft_fail",
                    f"item conformity is indeterminate or partial "
                    f"for: {name} (coverage in the indeterminate "
                    f"band routes to REVIEW)",
                    action="replace_item", expected=description,
                    actual=name, pointer=f"/items/{idx}/name"))
                break

    want_variant = instruction.get("variant") or \
        instruction.get("required_variant")
    if want_variant and items:
        got_variant = items[0].get("variant")
        if got_variant != want_variant:
            out.append(Result(
                "variant", "variant_mismatch", "hard_fail",
                f"variant {got_variant} differs from mandated "
                f"{want_variant}", action="change_variant",
                expected=want_variant, actual=got_variant))
    return out


# ------------------------------------------------------------------
# Booking
# ------------------------------------------------------------------

def booking_results(instruction, subject):
    out = []
    legs = subject.get("legs") or []

    mandated = [t.get("name") for t in instruction.get("travelers")
                or []]
    built = subject.get("travelers") or []
    if mandated:
        mset = {norm_name(n) for n in mandated}
        bset = {norm_name(n) for n in built}
        if mset != bset:
            missing = [n for n in mandated if norm_name(n) not in bset]
            extra = [n for n in built if norm_name(n) not in mset]
            out.append(Result(
                "travelers", "name_mismatch", "hard_fail",
                f"traveler names differ from the instruction: "
                f"expected {missing or mandated}, built "
                f"{extra or built}",
                action="correct_traveler_name",
                expected=missing[0] if missing else mandated,
                actual=extra[0] if extra else built))

    flex = instruction.get("date_flex_days") or 0
    date_checks = []
    if legs and instruction.get("departure_date"):
        date_checks.append(
            ("departure_date", instruction["departure_date"],
             legs[0].get("depart_at", "")[:10], 0))
    if legs and instruction.get("return_date"):
        date_checks.append(
            ("return_date", instruction["return_date"],
             legs[-1].get("depart_at", "")[:10], len(legs) - 1))
    for field, want, got, leg_idx in date_checks:
        if got and got != want:
            delta = abs((parse_ts(got) - parse_ts(want)).days)
            if delta > flex:
                pointer = f"/legs/{leg_idx}/depart_at"
                label = "departure" if field == "departure_date" \
                    else "return"
                out.append(Result(
                    "travel_dates", "date_mismatch", "hard_fail",
                    f"{label} date {got} differs from mandated "
                    f"{want} by {delta} day(s); flex is {flex}",
                    action="change_travel_date", expected=want,
                    actual=got, field=field, pointer=pointer))
                break

    if legs:
        # Origin is the first leg's departure; destination is the
        # OUTBOUND destination — the first leg's arrival. A round
        # trip's last leg flies home, so the final leg's arrival
        # is not the destination and is never compared to it.
        origin = (instruction.get("origin") or {}).get("airport")
        dest = (instruction.get("destination") or {}).get("airport")
        if origin and legs[0].get("from_airport") != origin:
            out.append(Result(
                "airports", "item_mismatch", "hard_fail",
                f"origin airport {legs[0].get('from_airport')} "
                f"differs from mandated {origin}; no silent "
                f"substitution", action="change_airport",
                expected=origin, actual=legs[0].get("from_airport"),
                pointer="/legs/0/from_airport"))
        elif dest and legs[0].get("to_airport") != dest:
            out.append(Result(
                "airports", "item_mismatch", "hard_fail",
                f"destination airport {legs[0].get('to_airport')} "
                f"differs from mandated {dest}; no silent "
                f"substitution", action="change_airport",
                expected=dest, actual=legs[0].get("to_airport"),
                pointer="/legs/0/to_airport"))

    fare = subject.get("fare") or {}
    if instruction.get("cabin") and fare.get("cabin") and \
            fare["cabin"].lower() != instruction["cabin"].lower():
        out.append(Result(
            "cabin", "cabin_mismatch", "hard_fail",
            f"cabin {fare['cabin']} differs from mandated "
            f"{instruction['cabin']}", action="change_cabin",
            expected=instruction["cabin"], actual=fare["cabin"]))

    terms = instruction.get("fare_terms") or {}
    if terms.get("refundability") == "refundable_required" and \
            fare.get("refundability") != "refundable":
        out.append(Result(
            "fare_terms", "fare_terms_mismatch", "hard_fail",
            f"fare refundability {fare.get('refundability')} does "
            f"not meet the mandated refundable requirement",
            action="change_fare_terms", expected="refundable",
            actual=fare.get("refundability"),
            pointer="/fare/refundability"))
    elif terms.get("max_change_fee") is not None and \
            (fare.get("change_fee") or 0) > terms["max_change_fee"]:
        out.append(Result(
            "fare_terms", "fare_terms_mismatch", "hard_fail",
            f"change fee {fare.get('change_fee')} exceeds the "
            f"mandated maximum {terms['max_change_fee']}",
            action="change_fare_terms",
            expected=terms["max_change_fee"],
            actual=fare.get("change_fee"), pointer="/fare/change_fee"))

    ceiling = money(instruction.get("max_total_price"))
    total = money((subject.get("price") or {}).get("total"))
    if ceiling is not None and total is not None and total > ceiling:
        out.append(Result(
            "price", "price_over_ceiling", "hard_fail",
            f"total {total} exceeds the instruction ceiling "
            f"{ceiling}", action="reduce_total", expected=ceiling,
            actual=total))

    cur = instruction.get("currency")
    if cur and subject.get("currency") and subject["currency"] != cur:
        out.append(Result(
            "currency", "currency_mismatch", "hard_fail",
            f"currency {subject['currency']} differs from mandated "
            f"{cur}", action="change_currency", expected=cur,
            actual=subject["currency"]))
    return out


# ------------------------------------------------------------------
# Reservation
# ------------------------------------------------------------------

def _minutes(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def reservation_results(instruction, subject):
    out = []

    want_provider = instruction.get("provider_name")
    if want_provider and subject.get("provider_name") and \
            norm_name(subject["provider_name"]) != \
            norm_name(want_provider):
        out.append(Result(
            "provider", "item_mismatch", "hard_fail",
            f"provider {subject['provider_name']} differs from "
            f"mandated {want_provider}", action="change_provider",
            expected=want_provider, actual=subject["provider_name"]))
    else:
        want_loc = instruction.get("location") or {}
        got_loc = subject.get("location") or {}
        loc_bad = False
        if want_loc.get("city") and got_loc.get("city") and \
                norm_name(want_loc["city"]) != norm_name(got_loc["city"]):
            loc_bad = True
        if want_loc.get("name") and got_loc.get("name") and \
                not (tokens(want_loc["name"]) &
                     tokens(got_loc["name"])):
            loc_bad = True
        if loc_bad:
            out.append(Result(
                "provider", "item_mismatch", "hard_fail",
                f"location {got_loc} differs from mandated "
                f"{want_loc}", action="change_location",
                expected=want_loc, actual=got_loc,
                pointer="/location"))

    if instruction.get("date") and subject.get("date") and \
            subject["date"] != instruction["date"]:
        window = instruction.get("date_window")
        code = "date_outside_window" if window else "date_mismatch"
        out.append(Result(
            "reservation_date", code, "hard_fail",
            f"reservation date {subject['date']} differs from "
            f"mandated {instruction['date']}", action="change_date",
            expected=instruction["date"], actual=subject["date"],
            field="date"))

    tol = instruction.get("time_tolerance_minutes") or 0
    if instruction.get("time") and subject.get("time"):
        diff = abs(_minutes(subject["time"]) -
                   _minutes(instruction["time"]))
        if diff > tol:
            out.append(Result(
                "reservation_time", "time_outside_tolerance",
                "hard_fail",
                f"reservation time {subject['time']} is {diff} "
                f"minutes from mandated {instruction['time']}; "
                f"tolerance is {tol}", action="change_time",
                expected=f"{instruction['time']} \u00b1{tol} min",
                actual=subject["time"], field="time"))

    if instruction.get("party_size") is not None and \
            subject.get("party_size") is not None and \
            subject["party_size"] != instruction["party_size"]:
        out.append(Result(
            "party_size", "party_size_mismatch", "hard_fail",
            f"party size {subject['party_size']} differs from "
            f"mandated {instruction['party_size']}",
            action="change_party_size",
            expected=instruction["party_size"],
            actual=subject["party_size"]))

    want_name = instruction.get("name_on_reservation")
    if want_name and subject.get("name_on_reservation") and \
            norm_name(subject["name_on_reservation"]) != \
            norm_name(want_name):
        out.append(Result(
            "reservation_name", "name_mismatch", "hard_fail",
            f"name on reservation "
            f"{subject['name_on_reservation']} differs from "
            f"mandated {want_name}",
            action="correct_reservation_name", expected=want_name,
            actual=subject["name_on_reservation"]))

    max_dep = money(instruction.get("max_deposit"))
    dep = money(subject.get("deposit_amount"))
    if max_dep is not None and dep is not None and dep > max_dep:
        out.append(Result(
            "deposit", "deposit_over_limit", "hard_fail",
            f"deposit {dep} exceeds the mandated maximum {max_dep}",
            action="reduce_deposit", expected=max_dep, actual=dep))

    ceiling = money(instruction.get("max_total_price"))
    total = money(subject.get("total_amount"))
    if ceiling is not None and total is not None and total > ceiling:
        out.append(Result(
            "price", "price_over_ceiling", "hard_fail",
            f"total {total} exceeds the instruction ceiling "
            f"{ceiling}", action="reduce_total", expected=ceiling,
            actual=total))

    want_terms = instruction.get("cancellation_terms")
    got_terms = subject.get("cancellation_terms")
    if want_terms and got_terms and \
            norm_name(str(want_terms)) != norm_name(str(got_terms)):
        out.append(Result(
            "cancellation_terms", "cancellation_terms_mismatch",
            "hard_fail",
            f"cancellation terms differ from the instruction",
            action="change_cancellation_terms", expected=want_terms,
            actual=got_terms))
    return out


KIND_CHECKS = {
    "cart": cart_results,
    "booking": booking_results,
    "reservation": reservation_results,
}


def infer_kind(instruction):
    if "departure_date" in instruction or "travelers" in instruction:
        return "booking"
    if "party_size" in instruction or "time_tolerance_minutes" in \
            instruction or "service_description" in instruction:
        return "reservation"
    return "cart"


def project_message(result, verdict):
    if not result.correctable:
        severity = "unrecoverable"
    elif result.buyer_approval:
        severity = "requires_buyer_review"  # Section 8: in any case
    elif verdict == "REVIEW":
        severity = "requires_buyer_review"
    else:
        severity = "recoverable"
    pointer = result.pointer
    if pointer is None and result.field in POINTER_BY_FIELD:
        pointer = POINTER_BY_FIELD[result.field]
    if pointer is None:
        pointer = POINTER_BY_DIMENSION.get(
            (result.kind, result.dimension), "")
    msg = {
        "type": "error",
        "code": f"{NS}.{result.code}",
        "severity": severity,
        "path": to_jsonpath(pointer) if pointer else "$",
        "content": result.content,
    }
    if not result.correctable:
        # Section 5.5: no repair exists; the message carries no
        # correction fields (the f07 projection pins this shape).
        return msg
    if result.action is not None:
        msg["expected"] = result.expected
        msg["actual"] = result.actual
        msg["action"] = result.action
        msg["uncertain"] = result.status == "soft_fail"
        msg["requires_buyer_approval"] = False
    elif result.buyer_approval:
        # No auto-applicable repair: the fix would widen what the
        # buyer authorized, so it goes back to the buyer (S.8).
        msg["expected"] = result.expected
        msg["actual"] = result.actual
        msg["uncertain"] = result.status == "soft_fail"
        msg["requires_buyer_approval"] = True
    return msg


def check(instruction, subject, *, kind=None, previous_record_id=None,
          issued_at=None, ttl_minutes=DEFAULT_TTL_MINUTES, secret=None):
    """Run one check. Returns the v0.2 checkout fragment:
    {"messages": [...], "com.provecart.conformity": {...}}."""
    kind = kind or infer_kind(instruction)
    now = parse_ts(issued_at) if issued_at else \
        datetime.now(timezone.utc)
    results = []
    for probe in (check_signature(instruction, secret),
                  check_expiry(instruction, now),
                  check_merchant(instruction, subject)):
        if probe is not None:
            probe.kind = kind
            results.append(probe)
    for r in KIND_CHECKS[kind](instruction, subject):
        r.kind = kind
        results.append(r)

    # Verdict (spec Section 6): a positively established violation
    # with an in-authorization repair (or no repair at all) BLOCKs;
    # an indeterminate dimension, or a failure whose only repair
    # needs the buyer, routes to REVIEW; nothing failing is MATCH.
    blocking = any(r.status == "hard_fail" and not r.buyer_approval
                   for r in results)
    if blocking:
        verdict = "BLOCK"
    elif results:
        verdict = "REVIEW"
    else:
        verdict = "MATCH"

    messages = [project_message(r, verdict) for r in results]

    mandate_ref = {"digest": digest_of(instruction)}
    if instruction.get("id"):
        mandate_ref["id"] = instruction["id"]
    if instruction.get("scheme"):
        mandate_ref["scheme"] = instruction["scheme"]
    elif instruction.get("signature"):
        mandate_ref["scheme"] = "hmac-sha256"

    subj_digest = digest_of(subject)
    record_id = str(uuid.uuid5(
        uuid.NAMESPACE_DNS,
        f"{mandate_ref['digest']}|{subj_digest}|"
        f"{previous_record_id or ''}"))
    conformity = {
        "verdict": verdict,
        "record_id": record_id,
        "mandate_ref": mandate_ref,
        "subject_digest": subj_digest,
        "issued_at": fmt_ts(now),
        "expires_at": fmt_ts(now + timedelta(minutes=ttl_minutes)),
        "previous_record_id": previous_record_id,
    }
    if any("action" in m for m in messages):
        conformity["max_attempts"] = instruction.get(
            "max_attempts", DEFAULT_MAX_ATTEMPTS)
    return {"messages": messages, NS: conformity}


def engine_error_fragment(instruction, subject, exc):
    """Spec Section 5.5: an engine error fails safe to REVIEW."""
    return {
        "messages": [{
            "type": "error",
            "code": f"{NS}.engine_error",
            "severity": "requires_buyer_review",
            "path": "$",
            "content": f"checker error: {exc}",
        }],
        NS: {
            "verdict": "REVIEW",
            "record_id": str(uuid.uuid5(
                uuid.NAMESPACE_DNS,
                f"{digest_of(instruction)}|{digest_of(subject)}"
                f"|engine-error")),
            "mandate_ref": {"digest": digest_of(instruction)},
            "subject_digest": digest_of(subject),
            "issued_at": fmt_ts(datetime.now(timezone.utc)),
            "expires_at": fmt_ts(datetime.now(timezone.utc) +
                                 timedelta(minutes=DEFAULT_TTL_MINUTES)),
            "previous_record_id": None,
        },
    }


# ------------------------------------------------------------------
# Consumer half (spec Sections 5.3, 6, 7, 8)
# ------------------------------------------------------------------

def consumer_decision(fragment, *, now=None):
    """Decide what a platform/agent does with a checker's output.

    Returns {"action": ..., "auto_apply": [...], "escalate": [...]}
    where action is one of: proceed, apply_repairs_and_resubmit,
    escalate_to_buyer, refuse_expired_recheck. The loop never
    partially applies around an escalation: if any message
    escalates, the whole outcome escalates (the reference
    consumer's rule).
    """
    conformity = fragment.get(NS) or {}
    verdict = conformity.get("verdict")
    now = now or datetime.now(timezone.utc)
    expires = conformity.get("expires_at")
    if expires and parse_ts(expires) <= now:
        return {"action": "refuse_expired_recheck",
                "auto_apply": [], "escalate": [],
                "reason": "verdict expired; re-check, never act on "
                          "a stale verdict"}
    if verdict == "MATCH":
        return {"action": "proceed", "auto_apply": [],
                "escalate": [], "reason": "MATCH"}
    auto, esc = [], []
    for msg in fragment.get("messages") or []:
        code = (msg.get("code") or "").rsplit(".", 1)[-1]
        if msg.get("severity") == "unrecoverable":
            esc.append(msg)
        elif msg.get("requires_buyer_approval"):
            esc.append(msg)      # Section 8: never auto-applied
        elif code not in KNOWN_CODES:
            esc.append(msg)      # Section 5.3: unknown code
        elif msg.get("action") is not None and \
                msg["action"] not in KNOWN_ACTIONS:
            esc.append(msg)      # Section 5.3: unknown action
        elif msg.get("action") is None:
            esc.append(msg)      # no repair offered; buyer decides
        else:
            auto.append(msg)
    if verdict == "REVIEW" or esc:
        return {"action": "escalate_to_buyer", "auto_apply": [],
                "escalate": esc + auto,
                "reason": "REVIEW, a non-correctable failure, an "
                          "unknown code/action, or a repair beyond "
                          "the buyer's authorization"}
    return {"action": "apply_repairs_and_resubmit",
            "auto_apply": auto, "escalate": [],
            "reason": "BLOCK with only in-authorization repairs; "
                      "resubmit as a new check within max_attempts"}


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    opts = {}
    for a in argv:
        if a.startswith("--") and "=" in a:
            k, v = a[2:].split("=", 1)
            opts[k] = v
    if args and args[0] == "decide":
        fragment = json.loads(open(args[1]).read())
        print(json.dumps(consumer_decision(fragment), indent=2))
        return 0
    if len(args) < 2:
        print(__doc__.split("Implementation notes")[0])
        return 2
    instruction = json.loads(open(args[0]).read())
    subject = json.loads(open(args[1]).read())
    try:
        out = check(
            instruction, subject,
            kind=opts.get("kind"),
            previous_record_id=opts.get("previous-record-id"),
            issued_at=opts.get("issued-at"),
            ttl_minutes=int(opts.get("ttl-minutes",
                                     DEFAULT_TTL_MINUTES)),
            secret=opts.get("secret"))
    except Exception as exc:  # fail safe, per spec Section 5.5
        out = engine_error_fragment(instruction, subject, exc)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
