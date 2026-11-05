#!/usr/bin/env python3
"""
Fixture battery for the standalone reference checker.

    python3 test_checker.py

Runs the checker (checker.py, Python standard library only) against
the eight shipped ACF conformance fixtures and compares its output
with the shipped v0.2 projections in
standards/fixtures/projections/ (generated from the reference
implementation by standards/validate_fixtures.py).

What is compared, and what is not — stated plainly:

* COMPARED EXACTLY: the verdict; and per message the code, the
  severity, the JSONPath, and every extension field the projection
  carries (expected, actual, action, uncertain,
  requires_buyer_approval), including which fields are absent (the
  f07 non-correctable shape). On the conformity object: verdict,
  max_attempts presence and value, and issued/expires window.
* VALIDATED: every emitted message and the conformity object
  against standards/acf-v0.2.schema.json (via `jsonschema` when
  installed; a structural fallback otherwise). The mandate and
  subject digests are recomputed from the scenario inputs and
  must match what the checker emitted (the binding is internal
  and verifiable); the record id must be deterministic across
  runs (the idempotency anchor, demonstrated offline).
* NOT COMPARED: `content` wording (the spec makes the structured
  fields govern; each implementation renders its own sentences),
  and the record_id / digest VALUES in the projections (the
  reference implementation's ids are random UUIDs and its digests
  cover its own stored artifacts; an offline checker derives its
  own deterministically from the two documents it was given).
* ONE DOCUMENTED DELTA: for f05 the shipped projection shows
  previous_record_id as null because the capture pipeline elided
  the field (see standards/generate_fixtures.py's trim). The
  scenario here supplies the chain link — this checker's own f04
  record id, the same flow the generator used against the API —
  and the test asserts the checker carries it, as spec Sections 4
  and 7 require.

Fixture f08 is a consumer-behavior fixture: the test runs the
checker's consumer half (consumer_decision) on it and asserts the
required behavior — escalate, never auto-apply, never treat an
unknown code or action as a pass.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STANDARDS = ROOT / "standards"
SCEN = HERE / "scenarios"
sys.path.insert(0, str(HERE))

import checker  # noqa: E402

ISSUED_AT = "2026-11-05T00:00:00Z"
EXT_FIELDS = ("expected", "actual", "action", "uncertain",
              "requires_buyer_approval")

failures = []


def check(name, cond, detail=""):
    print(f"{'PASS' if cond else 'FAIL'}  {name}" +
          (f"  {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)


def load(path):
    return json.loads(Path(path).read_text())


# --- schema validation (jsonschema preferred, structural fallback)
def make_validators():
    schema = load(STANDARDS / "acf-v0.2.schema.json")
    try:
        import jsonschema
        jsonschema.Draft202012Validator.check_schema(schema)
        msg_v = jsonschema.Draft202012Validator(
            {**schema["$defs"]["conformityMessage"],
             "$schema": "https://json-schema.org/draft/2020-12/schema"})
        obj_v = jsonschema.Draft202012Validator(
            {**schema["$defs"]["conformityObject"],
             "$schema": "https://json-schema.org/draft/2020-12/schema"})
        return (lambda m: not list(msg_v.iter_errors(m)),
                lambda o: not list(obj_v.iter_errors(o)),
                "jsonschema")
    except ImportError:
        import re
        code_re = re.compile(r"^com\.provecart\.conformity\.[a-z0-9_]+$")
        action_re = re.compile(r"^[a-z][a-z0-9_]*$")

        def msg_ok(m):
            return all(k in m for k in
                       ("type", "code", "severity", "content")) \
                and m["type"] in ("error", "warning", "info") \
                and m["severity"] in ("recoverable",
                                      "requires_buyer_review",
                                      "unrecoverable") \
                and code_re.match(m["code"]) is not None \
                and ("action" not in m or
                     action_re.match(m["action"]) is not None)

        def obj_ok(o):
            return all(k in o for k in
                       ("verdict", "record_id", "mandate_ref",
                        "subject_digest", "expires_at")) \
                and o["verdict"] in ("MATCH", "REVIEW", "BLOCK") \
                and "digest" in o["mandate_ref"]

        return msg_ok, obj_ok, "structural fallback"


def compare_fragment(fid, mine, shipped):
    my_obj = mine[checker.NS]
    sh_obj = shipped[checker.NS]
    check(f"{fid}: verdict matches projection",
          my_obj["verdict"] == sh_obj["verdict"],
          f"mine={my_obj['verdict']} shipped={sh_obj['verdict']}")
    check(f"{fid}: message count matches",
          len(mine["messages"]) == len(shipped["messages"]),
          f"mine={len(mine['messages'])} "
          f"shipped={len(shipped['messages'])}")
    for i, (mm, sm) in enumerate(zip(mine["messages"],
                                     shipped["messages"])):
        tag = f"{fid}: message[{i}] {sm['code'].rsplit('.', 1)[-1]}"
        for field in ("type", "code", "severity", "path"):
            check(f"{tag} {field}", mm.get(field) == sm.get(field),
                  f"mine={mm.get(field)!r} shipped={sm.get(field)!r}")
        check(f"{tag} content is a non-empty string",
              isinstance(mm.get("content"), str) and
              bool(mm["content"].strip()))
        for field in EXT_FIELDS:
            check(f"{tag} field {field} presence+value",
                  (field in mm) == (field in sm) and
                  mm.get(field) == sm.get(field),
                  f"mine={mm.get(field, '<absent>')!r} "
                  f"shipped={sm.get(field, '<absent>')!r}")
    check(f"{fid}: max_attempts presence+value",
          ("max_attempts" in my_obj) == ("max_attempts" in sh_obj)
          and my_obj.get("max_attempts") == sh_obj.get("max_attempts"))
    check(f"{fid}: issued/expires window matches projection",
          my_obj["issued_at"] == sh_obj["issued_at"] and
          my_obj["expires_at"] == sh_obj["expires_at"])


def main():
    msg_ok, obj_ok, mode = make_validators()
    print(f"schema validation mode: {mode}\n")

    record_ids = {}
    fragments = {}
    fixture_ids = ["f01-cart-match",
                   "f02-cart-block-price-quantity-item",
                   "f03-cart-review-indeterminate-item",
                   "f04-booking-block-wrong-date",
                   "f05-booking-corrected-resubmission-match",
                   "f06-reservation-block-time-outside-tolerance",
                   "f07-cart-block-excluded-merchant-noncorrectable"]
    for fid in fixture_ids:
        instruction = load(SCEN / f"{fid}.instruction.json")
        subject = load(SCEN / f"{fid}.subject.json")
        prev = None
        if fid.startswith("f05"):
            prev = record_ids["f04-booking-block-wrong-date"]
        out = checker.check(instruction, subject,
                            previous_record_id=prev,
                            issued_at=ISSUED_AT)
        fragments[fid] = out
        obj = out[checker.NS]
        record_ids[fid] = obj["record_id"]

        shipped = load(STANDARDS / "fixtures" / "projections" /
                       f"{fid}.v0.2.json")
        compare_fragment(fid, out, shipped)

        for m in out["messages"]:
            check(f"{fid}: emitted message validates against "
                  f"acf-v0.2.schema.json", msg_ok(m))
        check(f"{fid}: emitted conformity object validates "
              f"against acf-v0.2.schema.json", obj_ok(obj))
        check(f"{fid}: mandate digest binds the scenario "
              f"instruction",
              obj["mandate_ref"]["digest"] ==
              checker.digest_of(instruction))
        check(f"{fid}: subject digest binds the scenario subject",
              obj["subject_digest"] == checker.digest_of(subject))
        again = checker.check(instruction, subject,
                              previous_record_id=prev,
                              issued_at=ISSUED_AT)
        check(f"{fid}: record_id deterministic across runs "
              f"(idempotency anchor)",
              again[checker.NS]["record_id"] == obj["record_id"])
        if fid.startswith("f05"):
            check("f05: previous_record_id carries the f04 chain "
                  "link (shipped projection elides it — see "
                  "docstring)",
                  obj["previous_record_id"] ==
                  record_ids["f04-booking-block-wrong-date"])
        print()

    # --- f08: consumer behavior on unknown code/action
    f08 = load(STANDARDS / "fixtures" /
               "f08-consumer-unknown-code-and-action.json")
    frag08 = f08["response"]
    msg08 = frag08["messages"][0]
    check("f08: fixture message itself validates against the "
          "schema", msg_ok(msg08))
    check("f08: code is namespaced but not in the known vocabulary",
          msg08["code"].startswith("com.provecart.conformity.") and
          msg08["code"].rsplit(".", 1)[-1] not in checker.KNOWN_CODES)
    check("f08: action is not in the known action vocabulary",
          msg08["action"] not in checker.KNOWN_ACTIONS)
    decision = checker.consumer_decision(
        frag08, now=datetime(2026, 11, 5, 0, 5, tzinfo=timezone.utc))
    check("f08: consumer escalates and auto-applies nothing",
          decision["action"] == "escalate_to_buyer" and
          decision["auto_apply"] == [],
          str(decision))

    # --- consumer pins on the checker's own outputs
    d = checker.consumer_decision(
        fragments["f01-cart-match"],
        now=datetime(2026, 11, 5, 0, 5, tzinfo=timezone.utc))
    check("consumer: MATCH fragment -> proceed",
          d["action"] == "proceed")
    d = checker.consumer_decision(
        fragments["f02-cart-block-price-quantity-item"],
        now=datetime(2026, 11, 5, 0, 5, tzinfo=timezone.utc))
    check("consumer: f02 BLOCK -> apply repairs and resubmit "
          "(3 auto-applied, none escalated)",
          d["action"] == "apply_repairs_and_resubmit" and
          len(d["auto_apply"]) == 3 and d["escalate"] == [],
          str(d))
    d = checker.consumer_decision(
        fragments["f03-cart-review-indeterminate-item"],
        now=datetime(2026, 11, 5, 0, 5, tzinfo=timezone.utc))
    check("consumer: f03 REVIEW -> escalate to buyer",
          d["action"] == "escalate_to_buyer")
    d = checker.consumer_decision(
        fragments["f07-cart-block-excluded-merchant-noncorrectable"],
        now=datetime(2026, 11, 5, 0, 5, tzinfo=timezone.utc))
    check("consumer: f07 non-correctable -> escalate to buyer",
          d["action"] == "escalate_to_buyer")
    d = checker.consumer_decision(
        fragments["f01-cart-match"],
        now=datetime(2026, 11, 5, 1, 0, tzinfo=timezone.utc))
    check("consumer: expired verdict -> refuse and re-check",
          d["action"] == "refuse_expired_recheck")

    print()
    if failures:
        print(f"{len(failures)} FAILURE(S)")
        return 1
    print("ALL REFERENCE-CHECKER FIXTURE TESTS PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
