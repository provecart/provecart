# ACF v0.1 — Worked examples

Companion to the Agent Correction Format (ACF) v0.1 spec
(https://provecart.com/standards/correction-format). Four complete
checks, one per subject family and failure shape: the instruction
reference (mandate) as created, the subject as submitted, and the
verdict object exactly as the reference implementation returned it —
nothing elided, including the per-dimension `results` array the
spec's own Section 9 example leaves out.

Provenance: generated 2026-11-05 by the reference implementation
(the ProveCart verification API, production code) on a local test
instance. Mandate ids, record ids, hashes and tokens are from that
test instance; every shape, code and correction payload is the live
format. Example 1 is the same scenario the spec's Section 9 quotes
from a live production capture of 2026-11-04
(`standards/acf-live-example-20261104.json` in the project record);
this is its complete, unelided twin.

Machine-readable copies of all four examples live in `examples/`
beside this file; conformance vectors live in `test-vectors.json`.

---

## Example 1 — Cart mismatch (BLOCK, three corrections)

The buyer instructed: Sony WH-1000XM5 headphones, at most 1,
ceiling $300. The agent built a cart with two BassPro Q9
headphones at $378. Three dimensions fail; the verdict is BLOCK
and the response carries one correction per failing dimension.

Instruction reference as created:

```json
{
  "user_id": "user-123",
  "item_description": "Sony WH-1000XM5 wireless noise cancelling headphones",
  "item_keywords": [
    "sony",
    "wh-1000xm5",
    "wireless",
    "headphones",
    "noise",
    "cancelling"
  ],
  "brand": "Sony",
  "category": "electronics",
  "max_total_price": 300.0,
  "currency": "USD",
  "merchant_allowlist": [
    "shop.example.com"
  ],
  "max_quantity": 1,
  "expires_at": "2026-11-12T00:54:42.332564Z"
}
```

Subject as submitted:

```json
{
  "merchant": {
    "name": "Example Shop",
    "domain": "shop.example.com"
  },
  "items": [
    {
      "name": "BassPro Q9 Wireless Headphones",
      "variant": null,
      "quantity": 2,
      "unit_price": 189.0
    }
  ],
  "total_price": 378.0,
  "currency": "USD"
}
```

Verdict object returned:

```json
{
  "verdict": "BLOCK",
  "results": [
    {
      "dimension": "mandate_signature",
      "status": "pass",
      "reasons": [
        "mandate signature valid"
      ],
      "code": "MANDATE_SIGNATURE_VALID",
      "severity": "pass"
    },
    {
      "dimension": "mandate_expiry",
      "status": "pass",
      "reasons": [
        "mandate valid until 2026-11-12T00:54:42.332564Z"
      ],
      "code": "MANDATE_VALID",
      "severity": "pass"
    },
    {
      "dimension": "merchant",
      "status": "pass",
      "reasons": [
        "merchant is on the mandate allowlist"
      ],
      "code": "MERCHANT_OK",
      "severity": "pass"
    },
    {
      "dimension": "price",
      "status": "hard_fail",
      "reasons": [
        "total on the mandate basis (grand_total) exceeds the ceiling: compared figure 378.0 (merchandise 378.0 + tax 0.0 + shipping 0.0 + fees 0.0 = 378.0) vs ceiling 300.0 USD."
      ],
      "code": "PRICE_OVER_CEILING",
      "details": {
        "merchandise_total": 378.0,
        "tax": 0.0,
        "shipping": 0.0,
        "fees": 0.0,
        "total_incl_tax_fees": 378.0,
        "stated_total": 378.0,
        "basis": "grand_total",
        "compared_figure": 378.0,
        "ceiling": 300.0
      },
      "severity": "hard"
    },
    {
      "dimension": "currency",
      "status": "pass",
      "reasons": [
        "currency matches mandate"
      ],
      "code": "CURRENCY_MATCH",
      "severity": "pass"
    },
    {
      "dimension": "quantity",
      "status": "soft_fail",
      "reasons": [
        "total quantity 2 exceeds mandate max_quantity 1"
      ],
      "code": "QUANTITY_OVER_MAX",
      "severity": "soft"
    },
    {
      "dimension": "item_match",
      "status": "soft_fail",
      "reasons": [
        "item conformity is indeterminate or partial for: BassPro Q9 Wireless Headphones (coverage in the indeterminate band routes to REVIEW)"
      ],
      "code": "ITEM_INDETERMINATE",
      "details": {
        "per_item": [
          {
            "name": "BassPro Q9 Wireless Headphones",
            "coverage": 0.444,
            "jaccard": 0.364,
            "band": "indeterminate",
            "accessory": false
          }
        ]
      },
      "severity": "soft"
    },
    {
      "dimension": "brand",
      "status": "pass",
      "reasons": [
        "no cart item is positively identified as a brand other than 'Sony'"
      ],
      "code": "BRAND_OK",
      "severity": "pass"
    },
    {
      "dimension": "category",
      "status": "pass",
      "reasons": [
        "cart categories compatible with mandate category 'electronics'"
      ],
      "code": "CATEGORY_OK",
      "details": {
        "mandate_category": "electronics",
        "item_categories": {
          "BassPro Q9 Wireless Headphones": "audio"
        }
      },
      "severity": "pass"
    }
  ],
  "verdict_token": "eyJhbW91bnQiOjM3OC4wLCJjYXJ0X2hhc2giOiI3OGUzZmI2NTVjMjVhYzJmZDQ5MTg1N2Q2MjM4OTZiZmUxZmYwNGJiYzdhMzM3MmI2YWY2NGQyNzM0Mjg2ZmQyIiwiY3VycmVuY3kiOiJVU0QiLCJleHBpcmVzX2F0IjoiMjAyNi0xMS0wNVQwMTowOTo0My45NDgxNzZaIiwiaXNzdWVkX2F0IjoiMjAyNi0xMS0wNVQwMDo1NDo0My45NDgxNzZaIiwibWFuZGF0ZV9pZCI6ImJiODUyZmNiLTE0ZjYtNDExNy1iYjYxLWY0OTQzNmNjOWE2NSIsInJlY29yZF9pZCI6ImIyYTNjYzFlLTE3NmItNDI1YS05YzlkLTdiYTEzNTU4ZjliYyIsInZlcmRpY3QiOiJCTE9DSyJ9.e05b4fc90272b8943d8328763cc66605da21b33d01adaa8650245400e37b5791",
  "record_id": "b2a3cc1e-176b-425a-9c9d-7ba13558f9bc",
  "cart_hash": "78e3fb655c25ac2fd491857d623896bfe1ff04bbc7a3372b6af64d2734286fd2",
  "policy": {
    "fail_safe": true
  },
  "corrections": [
    {
      "dimension": "price",
      "action": "reduce_total",
      "reason": "total on the mandate basis (grand_total) exceeds the ceiling: compared figure 378.0 (merchandise 378.0 + tax 0.0 + shipping 0.0 + fees 0.0 = 378.0) vs ceiling 300.0 USD.",
      "expected": 300.0,
      "actual": 378.0
    },
    {
      "dimension": "quantity",
      "action": "reduce_quantity",
      "reason": "total quantity 2 exceeds mandate max_quantity 1",
      "expected": 1,
      "actual": 2
    },
    {
      "dimension": "item_match",
      "action": "replace_item",
      "item": "BassPro Q9 Wireless Headphones",
      "reason": "item conformity is indeterminate or partial for: BassPro Q9 Wireless Headphones (coverage in the indeterminate band routes to REVIEW)",
      "expected": "Sony WH-1000XM5 wireless noise cancelling headphones",
      "actual": "BassPro Q9 Wireless Headphones"
    }
  ],
  "max_attempts": 3,
  "agent_notice": "Help for this agent: agents that practice on ProveCart's free exam catch mistakes like this before a purchase is stopped, so their buyers get a smoother checkout. Free practice and certification: https://provecart.com/agents",
  "links": {
    "certification": "https://provecart.com/agents"
  }
}
```

The conforming repair: replace the item with the instructed Sony
headphones, quantity 1, total within $300 — resubmitted as a new
check against the same instruction reference with
`previous_record_id` set to this attempt's `record_id`.

---

## Example 2 — Price over ceiling (BLOCK, one correction)

The buyer instructed wireless noise-cancelling headphones, at
most 1, ceiling $300. The agent found the right item at the right
quantity — at $349.99. Only the price dimension fails, so the
response carries exactly one correction. This is the common case:
the fix is a cheaper equivalent or a price the buyer approves
(REVIEW route if the agent cannot bring the total down inside the
instructions).

Instruction reference as created:

```json
{
  "user_id": "user-123",
  "item_description": "Wireless noise cancelling over-ear headphones",
  "item_keywords": [
    "wireless",
    "headphones",
    "noise",
    "cancelling"
  ],
  "category": "electronics",
  "max_total_price": 300.0,
  "currency": "USD",
  "merchant_allowlist": [
    "shop.example.com"
  ],
  "merchant_blocklist": [
    "evil.example.com"
  ],
  "max_quantity": 1,
  "expires_at": "2026-11-12T00:54:42.332564Z"
}
```

Subject as submitted:

```json
{
  "merchant": {
    "name": "Example Shop",
    "domain": "shop.example.com"
  },
  "items": [
    {
      "name": "Wireless Noise-Cancelling Headphones",
      "variant": "black",
      "quantity": 1,
      "unit_price": 349.99
    }
  ],
  "total_price": 349.99,
  "currency": "USD"
}
```

Verdict object returned:

```json
{
  "verdict": "BLOCK",
  "results": [
    {
      "dimension": "mandate_signature",
      "status": "pass",
      "reasons": [
        "mandate signature valid"
      ],
      "code": "MANDATE_SIGNATURE_VALID",
      "severity": "pass"
    },
    {
      "dimension": "mandate_expiry",
      "status": "pass",
      "reasons": [
        "mandate valid until 2026-11-12T00:54:42.332564Z"
      ],
      "code": "MANDATE_VALID",
      "severity": "pass"
    },
    {
      "dimension": "merchant",
      "status": "pass",
      "reasons": [
        "merchant is on the mandate allowlist"
      ],
      "code": "MERCHANT_OK",
      "severity": "pass"
    },
    {
      "dimension": "price",
      "status": "hard_fail",
      "reasons": [
        "total on the mandate basis (grand_total) exceeds the ceiling: compared figure 349.99 (merchandise 349.99 + tax 0.0 + shipping 0.0 + fees 0.0 = 349.99) vs ceiling 300.0 USD."
      ],
      "code": "PRICE_OVER_CEILING",
      "details": {
        "merchandise_total": 349.99,
        "tax": 0.0,
        "shipping": 0.0,
        "fees": 0.0,
        "total_incl_tax_fees": 349.99,
        "stated_total": 349.99,
        "basis": "grand_total",
        "compared_figure": 349.99,
        "ceiling": 300.0
      },
      "severity": "hard"
    },
    {
      "dimension": "currency",
      "status": "pass",
      "reasons": [
        "currency matches mandate"
      ],
      "code": "CURRENCY_MATCH",
      "severity": "pass"
    },
    {
      "dimension": "quantity",
      "status": "pass",
      "reasons": [
        "total quantity 1 within max 1"
      ],
      "code": "QUANTITY_WITHIN_MAX",
      "severity": "pass"
    },
    {
      "dimension": "item_match",
      "status": "pass",
      "reasons": [
        "all cart items are strong matches for the mandate item specification (coverage 75%)"
      ],
      "code": "ITEM_MATCH",
      "details": {
        "per_item": [
          {
            "name": "Wireless Noise-Cancelling Headphones",
            "coverage": 0.75,
            "jaccard": 0.667,
            "band": "strong",
            "accessory": false
          }
        ]
      },
      "severity": "pass"
    },
    {
      "dimension": "category",
      "status": "pass",
      "reasons": [
        "cart categories compatible with mandate category 'electronics'"
      ],
      "code": "CATEGORY_OK",
      "details": {
        "mandate_category": "electronics",
        "item_categories": {
          "Wireless Noise-Cancelling Headphones": "audio"
        }
      },
      "severity": "pass"
    }
  ],
  "verdict_token": "eyJhbW91bnQiOjM0OS45OSwiY2FydF9oYXNoIjoiMzU3M2VhYWZkNjk5NmMxNWUwYmI4M2Q2ZDkyMTIzMTgwODExY2VlZDJjNGJmOTdhY2EwZTdmYTYwZTNmZGE3OSIsImN1cnJlbmN5IjoiVVNEIiwiZXhwaXJlc19hdCI6IjIwMjYtMTEtMDVUMDE6MDk6NDMuOTYxMzUwWiIsImlzc3VlZF9hdCI6IjIwMjYtMTEtMDVUMDA6NTQ6NDMuOTYxMzUwWiIsIm1hbmRhdGVfaWQiOiIzODU4NGY4MC1kYjNjLTRiMDMtOWViNi05MDYzMmMyNWJmYTAiLCJyZWNvcmRfaWQiOiI5ODk4MTlhZC0wODYwLTQ3OTctYWUzOC03MGZjN2QzMTBmNWEiLCJ2ZXJkaWN0IjoiQkxPQ0sifQ.d9f655db1bd3fe7f8a2ca387e77f309dc3b7d73feebcae435fdf71c465f3ab7f",
  "record_id": "989819ad-0860-4797-ae38-70fc7d310f5a",
  "cart_hash": "3573eaafd6996c15e0bb83d6d92123180811ceed2c4bf97aca0e7fa60e3fda79",
  "policy": {
    "fail_safe": true
  },
  "corrections": [
    {
      "dimension": "price",
      "action": "reduce_total",
      "reason": "total on the mandate basis (grand_total) exceeds the ceiling: compared figure 349.99 (merchandise 349.99 + tax 0.0 + shipping 0.0 + fees 0.0 = 349.99) vs ceiling 300.0 USD.",
      "expected": 300.0,
      "actual": 349.99
    }
  ],
  "max_attempts": 3,
  "agent_notice": "Help for this agent: agents that practice on ProveCart's free exam catch mistakes like this before a purchase is stopped, so their buyers get a smoother checkout. Free practice and certification: https://provecart.com/agents",
  "links": {
    "certification": "https://provecart.com/agents"
  }
}
```

### The sealed-record pointer, followed

`record_id` in the verdict object is the pointer into the sealed
evidence log (spec Section 8). Fetching that record returns the
full check — instruction reference, subject, results, corrections,
verdict — chained to the previous record by hash. Excerpt of the
record for this example (fetch status 200):

```json
{
  "record_id": "989819ad-0860-4797-ae38-70fc7d310f5a",
  "seq": 2,
  "timestamp": "2026-11-05T00:54:43.961350Z",
  "mandate_id": "38584f80-db3c-4b03-9eb6-90632c25bfa0",
  "verdict": "BLOCK",
  "cart_hash": "3573eaafd6996c15e0bb83d6d92123180811ceed2c4bf97aca0e7fa60e3fda79",
  "prev_hash": "7ec3d98140844012d7ceb375312fefb4ff7f31cbf140bda077bede4e9ee62870",
  "hash": "ec476af8dbe68bae0715fd12b44e1817a8f18b81c44c9a7c6c00c304ed2f6768",
  "supersedes": null,
  "(remaining fields)": "mandate, subject, results, corrections, totals, policy \u2014 the full check, as submitted and as decided"
}
```

The full record exports as a dispute bundle via
`GET /records/{record_id}/export`. A corrected resubmission
links back through the record's `supersedes` field, so the chain
of attempts is itself the evidence.

---

## Example 3 — Reservation time outside tolerance (BLOCK, one correction)

The customer instructed: dinner for four at Chez Nous Downtown,
2026-12-10 at 19:00, with a stated tolerance of 15 minutes. The
agent booked 19:45 — 45 minutes off, outside the tolerance the
customer themselves stated. One correction: `change_time`, with
the expected value carrying the tolerance (`19:00 ±15 min`).

Instruction reference as created:

```json
{
  "user_id": "user-123",
  "service_description": "Dinner reservation for four",
  "provider_name": "Chez Nous",
  "location": {
    "name": "Chez Nous Downtown",
    "city": "San Francisco"
  },
  "date": "2026-12-10",
  "time": "19:00",
  "time_tolerance_minutes": 15,
  "party_size": 4,
  "party_size_max": 6,
  "name_on_reservation": "Arash Tadi",
  "max_deposit": 50,
  "max_total_price": 300,
  "cancellation": {
    "free_until_hours_before": 24,
    "max_cancellation_fee": 25
  },
  "expires_at": "2026-11-12T00:54:42.332564Z"
}
```

Subject as submitted:

```json
{
  "merchant": {
    "name": "ResPlatform",
    "domain": "res.example.com"
  },
  "provider_name": "Chez Nous",
  "location": {
    "name": "Chez Nous Downtown",
    "city": "San Francisco"
  },
  "date": "2026-12-10",
  "time": "19:45",
  "party_size": 4,
  "name_on_reservation": "Arash Tadi",
  "deposit_amount": 25.0,
  "total_amount": 180.0,
  "currency": "USD",
  "cancellation": {
    "free_cancellation_hours_before": 48,
    "cancellation_fee": 0.0
  }
}
```

Verdict object returned:

```json
{
  "verdict": "BLOCK",
  "results": [
    {
      "dimension": "mandate_signature",
      "status": "pass",
      "reasons": [
        "mandate signature valid"
      ],
      "code": "MANDATE_SIGNATURE_VALID"
    },
    {
      "dimension": "mandate_expiry",
      "status": "pass",
      "reasons": [
        "mandate valid until 2026-11-12T00:54:42.332564Z"
      ],
      "code": "MANDATE_VALID"
    },
    {
      "dimension": "merchant",
      "status": "pass",
      "reasons": [
        "no merchant list restriction violated"
      ],
      "code": "MERCHANT_OK"
    },
    {
      "dimension": "provider",
      "status": "pass",
      "reasons": [
        "provider 'Chez Nous' matches the mandated 'Chez Nous'"
      ],
      "code": "PROVIDER_MATCH"
    },
    {
      "dimension": "location",
      "status": "pass",
      "reasons": [
        "location is consistent with the mandate"
      ],
      "code": "LOCATION_MATCH"
    },
    {
      "dimension": "reservation_date",
      "status": "pass",
      "reasons": [
        "reservation date 2026-12-10 matches the mandate"
      ],
      "code": "DATE_MATCH"
    },
    {
      "dimension": "reservation_time",
      "status": "hard_fail",
      "reasons": [
        "reservation time 19:45 is 45 minutes from mandated 19:00; tolerance is 15"
      ],
      "code": "TIME_OUTSIDE_TOLERANCE",
      "details": {
        "issues": [
          {
            "action": "change_time",
            "field": "time",
            "expected": "19:00 \u00b115 min",
            "actual": "19:45"
          }
        ]
      }
    },
    {
      "dimension": "party_size",
      "status": "pass",
      "reasons": [
        "party size 4 matches the mandate"
      ],
      "code": "PARTY_SIZE_MATCH"
    },
    {
      "dimension": "reservation_name",
      "status": "pass",
      "reasons": [
        "name on the reservation matches the mandate"
      ],
      "code": "RESERVATION_NAME_MATCH"
    },
    {
      "dimension": "deposit",
      "status": "pass",
      "reasons": [
        "deposit 25.0 is within the mandate's maximum 50.0"
      ],
      "code": "DEPOSIT_WITHIN_LIMIT"
    },
    {
      "dimension": "price",
      "status": "pass",
      "reasons": [
        "reservation total 180.0 is within the ceiling 300.0 USD"
      ],
      "code": "PRICE_WITHIN_CEILING",
      "details": {
        "total_incl_tax_fees": 180.0,
        "compared_figure": 180.0,
        "ceiling": 300.0
      }
    },
    {
      "dimension": "cancellation_terms",
      "status": "pass",
      "reasons": [
        "free cancellation until 48h before meets the mandate (24h)",
        "cancellation fee 0.0 is within the mandate's maximum 25"
      ],
      "code": "CANCELLATION_TERMS_OK"
    },
    {
      "dimension": "currency",
      "status": "pass",
      "reasons": [
        "currency matches mandate"
      ],
      "code": "CURRENCY_MATCH"
    }
  ],
  "verdict_token": "eyJhbW91bnQiOjE4MC4wLCJjYXJ0X2hhc2giOiI4ZDAyNzU4MDM4MGQ1ODg0ZTY3NjY1YWQ1Nzc5MTE4NmE0NDlkZWYzZjE2NDFjZGM0NjEzNmQzMzhjZjVhZGNjIiwiY3VycmVuY3kiOiJVU0QiLCJleHBpcmVzX2F0IjoiMjAyNi0xMS0wNVQwMTowOTo0My45NzUzODJaIiwiaXNzdWVkX2F0IjoiMjAyNi0xMS0wNVQwMDo1NDo0My45NzUzODJaIiwibWFuZGF0ZV9pZCI6IjM0Yjc5ZTAyLTA1MzQtNGVjOC1hNGZlLTMwM2MzY2EyMzZhNSIsInJlY29yZF9pZCI6IjZhMDg3ODkwLTBlNTAtNDgxNy05MWUxLTEzN2Q5ZTcxMjdmNCIsInZlcmRpY3QiOiJCTE9DSyJ9.d217b902beee0c55265034632b58e00966f093460f8361207db1f79b7dfd3237",
  "record_id": "6a087890-0e50-4817-91e1-137d9e7127f4",
  "cart_hash": "8d027580380d5884e67665ad57791186a449def3f1641cdc46136d338cf5adcc",
  "policy": {
    "fail_safe": true
  },
  "corrections": [
    {
      "dimension": "reservation_time",
      "action": "change_time",
      "reason": "reservation time 19:45 is 45 minutes from mandated 19:00; tolerance is 15",
      "expected": "19:00 \u00b115 min",
      "actual": "19:45",
      "field": "time"
    }
  ],
  "max_attempts": 3,
  "gates": {
    "payment_capture": "deny",
    "confirmation": "deny"
  },
  "agent_notice": "Help for this agent: agents that practice on ProveCart's free exam catch mistakes like this before a purchase is stopped, so their buyers get a smoother checkout. Free practice and certification: https://provecart.com/agents",
  "links": {
    "certification": "https://provecart.com/agents"
  }
}
```

---

## Example 4 — Booking traveler name (REVIEW, one correction)

The customer instructed travel for "Maria Elena Garcia". The
agent booked "Maria Garcia" — the middle name dropped. A name-form
difference is not proof of a different person, so the verdict is
REVIEW, not BLOCK: the correction (`correct_traveler_name`) is
offered, and the buyer-escalation rule (spec Section 6) governs —
an agent may auto-apply a correction that restores conformity
with the signed instructions; it may never silently accept a
different traveler.

Instruction reference as created:

```json
{
  "user_id": "user-123",
  "travelers": [
    {
      "name": "Maria Elena Garcia"
    },
    {
      "name": "James Robert Smith"
    }
  ],
  "origin": {
    "airport": "SFO"
  },
  "destination": {
    "airport": "JFK"
  },
  "acceptable_alternates_destination": [
    "LGA"
  ],
  "departure_date": "2026-12-10",
  "return_date": "2026-12-15",
  "cabin": "economy",
  "fare_terms": {
    "refundability": "refundable_required",
    "max_change_fee": 75
  },
  "max_connections": 1,
  "min_connection_minutes": 45,
  "max_layover_minutes": 360,
  "max_total_price": 1200,
  "price_basis": "all_in",
  "expires_at": "2026-11-12T00:54:42.332564Z"
}
```

Subject as submitted:

```json
{
  "merchant": {
    "name": "AirSeller",
    "domain": "air.example.com"
  },
  "travelers": [
    "Maria Garcia",
    "James Robert Smith"
  ],
  "legs": [
    {
      "carrier": "UA",
      "flight_number": "UA100",
      "from_airport": "SFO",
      "to_airport": "JFK",
      "depart_at": "2026-12-10T08:00:00-08:00",
      "arrive_at": "2026-12-10T16:30:00-05:00"
    },
    {
      "carrier": "UA",
      "flight_number": "UA101",
      "from_airport": "JFK",
      "to_airport": "ORD",
      "depart_at": "2026-12-15T09:00:00-05:00",
      "arrive_at": "2026-12-15T11:00:00-06:00"
    },
    {
      "carrier": "UA",
      "flight_number": "UA102",
      "from_airport": "ORD",
      "to_airport": "SFO",
      "depart_at": "2026-12-15T12:30:00-06:00",
      "arrive_at": "2026-12-15T15:05:00-08:00"
    }
  ],
  "fare": {
    "cabin": "economy",
    "refundability": "refundable",
    "change_fee": 0
  },
  "price": {
    "total": 980.0,
    "base_fare": 800.0,
    "taxes": 120.0,
    "carrier_fees": 60.0,
    "ancillaries": 0.0
  },
  "currency": "USD"
}
```

Verdict object returned:

```json
{
  "verdict": "REVIEW",
  "results": [
    {
      "dimension": "mandate_signature",
      "status": "pass",
      "reasons": [
        "mandate signature valid"
      ],
      "code": "MANDATE_SIGNATURE_VALID"
    },
    {
      "dimension": "mandate_expiry",
      "status": "pass",
      "reasons": [
        "mandate valid until 2026-11-12T00:54:42.332564Z"
      ],
      "code": "MANDATE_VALID"
    },
    {
      "dimension": "merchant",
      "status": "pass",
      "reasons": [
        "no merchant list restriction violated"
      ],
      "code": "MERCHANT_OK"
    },
    {
      "dimension": "traveler_name",
      "status": "soft_fail",
      "reasons": [
        "booked traveler 'Maria Garcia' vs mandated 'Maria Elena Garcia': booked name omits middle name(s) \u2014 routes to REVIEW"
      ],
      "code": "TRAVELER_NAME_FORM_DIFFERENCE",
      "details": {
        "issues": [
          {
            "action": "correct_traveler_name",
            "field": "travelers",
            "expected": "Maria Elena Garcia",
            "actual": "Maria Garcia"
          }
        ]
      }
    },
    {
      "dimension": "airports",
      "status": "pass",
      "reasons": [
        "origin: airport SFO matches the mandate",
        "destination: airport JFK matches the mandate"
      ],
      "code": "AIRPORT_OK"
    },
    {
      "dimension": "travel_dates",
      "status": "pass",
      "reasons": [
        "departure date 2026-12-10 within 0 day(s) of mandated 2026-12-10",
        "return date 2026-12-15 within 0 day(s) of mandated 2026-12-15"
      ],
      "code": "DATE_MATCH"
    },
    {
      "dimension": "itinerary_structure",
      "status": "pass",
      "reasons": [
        "itinerary structure satisfies the mandate's connection constraints"
      ],
      "code": "ITINERARY_OK"
    },
    {
      "dimension": "cabin",
      "status": "pass",
      "reasons": [
        "booked cabin 'economy' meets the mandated 'economy'"
      ],
      "code": "CABIN_OK"
    },
    {
      "dimension": "fare_terms",
      "status": "pass",
      "reasons": [
        "booked fare refundability 'refundable' satisfies the mandate (refundable_required)",
        "change fee 0.0 is within the mandate's maximum 75"
      ],
      "code": "TERMS_OK"
    },
    {
      "dimension": "price",
      "status": "pass",
      "reasons": [
        "total on the mandate basis (all_in) is 980.0, within ceiling 1200.0 USD"
      ],
      "code": "PRICE_WITHIN_CEILING",
      "details": {
        "total_incl_tax_fees": 980.0,
        "booking_total": 980.0,
        "base_fare": 800.0,
        "taxes": 120.0,
        "carrier_fees": 60.0,
        "ancillaries": 0.0,
        "basis": "all_in",
        "compared_figure": 980.0,
        "ceiling": 1200.0
      }
    },
    {
      "dimension": "currency",
      "status": "pass",
      "reasons": [
        "currency matches mandate"
      ],
      "code": "CURRENCY_MATCH"
    }
  ],
  "verdict_token": "eyJhbW91bnQiOjk4MC4wLCJjYXJ0X2hhc2giOiI4OTczMzg3YjdiYjZlOTcwY2QxYWE2NjdkOWY2NjhlYWJjOGFkMjAxMjdmYWZiZDI0MTUxNWZhNDExMjEwNjdmIiwiY3VycmVuY3kiOiJVU0QiLCJleHBpcmVzX2F0IjoiMjAyNi0xMS0wNVQwMTowOTo0NC4wMDAzMzVaIiwiaXNzdWVkX2F0IjoiMjAyNi0xMS0wNVQwMDo1NDo0NC4wMDAzMzVaIiwibWFuZGF0ZV9pZCI6IjczZjRjZmM0LWNmZWUtNGNlMi04OGNmLTU2MWVjOTIwOThhNSIsInJlY29yZF9pZCI6IjVmY2Y1MzYzLTZmMTYtNDc5NC1hMzI4LTU2OGViNGNlODhiOSIsInZlcmRpY3QiOiJSRVZJRVcifQ.5e39c9eab89101c7d4053f13332768704013171bf53eb15a7d6aab9b6c603e0f",
  "record_id": "5fcf5363-6f16-4794-a328-568eb4ce88b9",
  "cart_hash": "8973387b7bb6e970cd1aa667d9f668eabc8ad20127fafbd241515fa41121067f",
  "policy": {
    "fail_safe": true
  },
  "corrections": [
    {
      "dimension": "traveler_name",
      "action": "correct_traveler_name",
      "reason": "booked traveler 'Maria Garcia' vs mandated 'Maria Elena Garcia': booked name omits middle name(s) \u2014 routes to REVIEW",
      "expected": "Maria Elena Garcia",
      "actual": "Maria Garcia",
      "field": "travelers"
    }
  ],
  "max_attempts": 3,
  "gates": {
    "payment_capture": "review",
    "ticket_issuance": "review"
  },
  "ai_adjudication": {
    "provider": "none",
    "model": null,
    "rules_verdict": "REVIEW",
    "codes": [
      "TRAVELER_NAME_FORM_DIFFERENCE"
    ],
    "min_confidence": 0.85,
    "status": "unavailable",
    "outcome": "UPHELD",
    "reasoning": "AI layer not configured on this deployment; the rules verdict stands."
  },
  "rules_verdict": "REVIEW",
  "agent_notice": "Help for this agent: agents that practice on ProveCart's free exam catch mistakes like this before a purchase is stopped, so their buyers get a smoother checkout. Free practice and certification: https://provecart.com/agents",
  "links": {
    "certification": "https://provecart.com/agents"
  }
}
```

---

## Reading these examples

- `corrections` appears only on REVIEW or BLOCK, and only for
  dimensions the agent can repair by editing the subject.
  Non-correctable failures (blocklisted merchant, expired or
  unsigned instruction reference) emit no correction and mark the
  dimension `"correctable": false` — see vectors V06 and V07 in
  `test-vectors.json`.
- `expected` is always a value from the buyer's own signed
  instructions; `actual` is the value found in the subject. The
  payload never exposes checker internals.
- Every response carries `record_id` and a single-use,
  hold-bound `verdict_token` (spec Section 8).
