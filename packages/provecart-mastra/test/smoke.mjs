// Offline smoke test for provecart-mastra. Hand-rolled harness, no
// network, no test framework. Run: npm test  (builds, then runs this)
import assert from "node:assert";
import {
  FakeProveCartClient,
  routeVerdict,
  withProveCartCheck,
  wrapMastraTool,
} from "../dist/index.js";

let passed = 0;
const ok = (name) => { passed++; console.log(`ok - ${name}`); };

// Routing
assert.equal(routeVerdict({ verdict: "MATCH", record_id: "r1" }).decision, "proceed");
assert.equal(
  routeVerdict({ verdict: "BLOCK", corrections: [{ action: "remove_item" }] }).decision,
  "fix",
);
assert.equal(
  routeVerdict({ verdict: "BLOCK", corrections: [{ action: "widen_budget" }] }).decision,
  "escalate",
);
assert.equal(routeVerdict({ verdict: "REVIEW" }).decision, "escalate");
assert.equal(routeVerdict({ verdict: "???" }).decision, "escalate");
ok("routeVerdict: MATCH proceeds, known BLOCK fixes, the rest escalates");

const cartInput = {
  mandate_id: "m1",
  merchant: { name: "Shop" },
  items: [{ name: "Chair" }],
  total_price: 10,
};

// MATCH: wrapped tool executes
{
  let ran = 0;
  const fake = new FakeProveCartClient();
  const tool = wrapMastraTool(
    { id: "place_order", description: "demo", execute: async () => { ran++; return { placed: true }; } },
    { client: fake, kind: "cart" },
  );
  const out = await tool.execute(cartInput);
  assert.deepEqual(out, { placed: true });
  assert.equal(ran, 1);
  assert.equal(fake.calls[0].kind, "cart");
  ok("MATCH lets the wrapped tool run");
}

// BLOCK with known fix: wrapped tool does not execute
{
  let ran = 0;
  const fake = new FakeProveCartClient({
    verdict: "BLOCK", record_id: "r9", max_attempts: 2,
    corrections: [{ action: "reduce_quantity" }],
  });
  const tool = wrapMastraTool(
    { id: "place_order", execute: async () => { ran++; return { placed: true }; } },
    { client: fake },
  );
  const out = await tool.execute(cartInput);
  assert.equal(ran, 0);
  assert.equal(out.provecart_blocked, true);
  assert.equal(out.provecart_decision, "fix");
  assert.deepEqual(out.corrections, [{ action: "reduce_quantity" }]);
  assert.equal(out.record_id, "r9");
  ok("BLOCK returns a refusal carrying corrections; tool skipped");
}

// REVIEW escalates; booking kind routes to check_booking
{
  const fake = new FakeProveCartClient({ verdict: "REVIEW", corrections: [] });
  const wrapped = withProveCartCheck(async () => ({ booked: true }), { client: fake, kind: "booking" });
  const out = await wrapped({ booking: { mandate_id: "m" } });
  assert.equal(out.provecart_decision, "escalate");
  assert.equal(out.check_kind, "booking");
  assert.equal(fake.calls[0].kind, "booking");
  ok("REVIEW escalates and booking checks route correctly");
}

// Check failure escalates, never proceeds
{
  const boom = { check_cart: async () => { throw new Error("down"); } };
  const wrapped = withProveCartCheck(async () => ({ placed: true }), { client: boom });
  const out = await wrapped(cartInput);
  assert.equal(out.provecart_decision, "escalate");
  ok("a failed check escalates instead of proceeding");
}

console.log(`\n${passed} smoke groups passed`);
