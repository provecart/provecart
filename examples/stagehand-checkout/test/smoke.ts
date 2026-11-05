/**
 * Offline smoke test: all three verdict paths, really run.
 *
 *   npm run smoke
 *
 * Spins up the local fake verdict server on 127.0.0.1 and runs the
 * real interlock (checkBeforeCheckout) with the real client over
 * real HTTP for each scenario, asserting:
 *
 *   match : MATCH on the first check, buy clicked exactly once.
 *   fix   : BLOCK (wrong size) -> change_variant correction applied
 *           -> re-check carries previous_record_id -> MATCH ->
 *           buy clicked exactly once, on the corrected cart.
 *   review: REVIEW (item outside the mandate) -> flow stops, buy
 *           NEVER clicked, one escalation recorded.
 *
 * Plus a guard: a BLOCK whose corrections contain an unknown action
 * escalates instead of applying anything.
 *
 * No network beyond 127.0.0.1. No real merchant. Exit code 1 on any
 * failed assertion.
 */
import assert from "node:assert";
import { ProveCartClient, routeVerdict } from "../src/provecart.js";
import { checkBeforeCheckout } from "../src/checkBeforeCheckout.js";
import { startMockProveCart, handlePost } from "../src/mockProveCart.js";
import { SimulatedDriver } from "../src/drivers.js";
import { MANDATE_FIELDS, SCENARIO_CHOICES, type Scenario } from "../src/index.js";

async function run(scenario: Scenario) {
  const mock = await startMockProveCart();
  try {
    // Wrap fetch-level transport so we can observe previous_record_id.
    const seen: Record<string, unknown>[] = [];
    const client = new ProveCartClient({
      apiKey: "mock-key",
      baseUrl: mock.baseUrl,
      transport: async (path, body) => {
        if (path === "/verify") seen.push({ ...body });
        const res = await fetch(mock.baseUrl + path, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-API-Key": "mock-key" },
          body: JSON.stringify(body),
        });
        return { status: res.status, json: (await res.json()) as Record<string, unknown> };
      },
    });
    const mandate = await client.createMandate(MANDATE_FIELDS);
    const driver = new SimulatedDriver();
    await driver.buildCart(SCENARIO_CHOICES[scenario]);
    const result = await checkBeforeCheckout({
      client,
      mandateId: String(mandate.id),
      hooks: driver,
    });
    return { result, driver, seen };
  } finally {
    mock.server.close();
  }
}

async function main() {
  // 1) MATCH -> proceed to the buy click.
  {
    const { result, driver } = await run("match");
    assert.equal(result.outcome, "purchased");
    assert.equal(result.attempts, 1);
    assert.equal(driver.buyClicks, 1);
    assert.equal(driver.escalations.length, 0);
    console.log("PASS match : MATCH on check #1, buy clicked exactly once");
  }

  // 2) BLOCK -> in-authorization fix -> re-check with
  //    previous_record_id -> MATCH -> buy.
  {
    const { result, driver, seen } = await run("fix");
    assert.equal(result.outcome, "purchased");
    assert.equal(result.attempts, 2);
    assert.equal(driver.buyClicks, 1);
    assert.equal(seen.length, 2);
    assert.equal(seen[0].previous_record_id, undefined);
    assert.ok(
      typeof seen[1].previous_record_id === "string" &&
        (seen[1].previous_record_id as string).startsWith("rec_mock_"),
      "second check must carry previous_record_id from the BLOCK",
    );
    const cart = await driver.readCart();
    assert.equal(cart.items[0].variant, "US 10", "correction changed the size to the authorized US 10");
    console.log(
      `PASS fix   : BLOCK -> change_variant US 9->US 10 -> re-check (previous_record_id=${String(seen[1].previous_record_id)}) -> MATCH, buy clicked once`,
    );
  }

  // 3) REVIEW -> stop and ask the buyer; buy never clicked.
  {
    const { result, driver } = await run("review");
    assert.equal(result.outcome, "escalated");
    assert.equal(driver.buyClicks, 0, "buy must never be clicked on REVIEW");
    assert.equal(driver.escalations.length, 1);
    console.log(
      `PASS review: REVIEW -> halted, buy clicks = 0, escalated ("${driver.escalations[0]}")`,
    );
  }

  // 4) Guard: BLOCK with an unknown correction action escalates;
  //    nothing is applied, nothing is bought.
  {
    const routed = routeVerdict({
      verdict: "BLOCK",
      record_id: "rec_x",
      corrections: [{ action: "widen_authorization", field: "max_total_price" }],
    });
    assert.equal(routed.decision, "escalate");
    // And the in-process mock agrees the wire shape is stable:
    const direct = handlePost("/mandates", { ...MANDATE_FIELDS });
    assert.equal(direct.status, 200);
    console.log("PASS guard : BLOCK with unknown correction action -> escalate, never applied");
  }

  console.log("SMOKE OK: 4/4 paths behave (match, block->fix->match, review->halt, unknown-action guard)");
}

main().catch((err) => {
  console.error("SMOKE FAILED:", err);
  process.exit(1);
});
