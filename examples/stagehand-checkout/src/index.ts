/**
 * ProveCart x Stagehand: check before checkout.
 *
 * A browser agent assembles a cart on a local demo store page, and
 * the buy click is gated by ProveCart:
 *
 *   MATCH  -> the buy click happens
 *   BLOCK  -> apply only the in-authorization corrections, re-check
 *             with previous_record_id, buy only on the later MATCH
 *   REVIEW -> stop and ask the buyer; the buy click never happens
 *
 * Default mode is fully offline: a local fake verdict server
 * (mockProveCart.ts) answers on 127.0.0.1 and a simulated driver
 * plays the page. Live mode is an explicit opt-in:
 *
 *   PROVECART_LIVE=1 PROVECART_API_KEY=... npm start
 *     -> checks go to https://api.provecart.com
 *   STAGEHAND_LIVE=1 npm start
 *     -> a real Stagehand session drives demo/demo-store.html
 *        (still a local page; still no real merchant, ever)
 *
 * Run one scenario:  npm start -- match | fix | review
 */
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { ProveCartClient } from "./provecart.js";
import { checkBeforeCheckout } from "./checkBeforeCheckout.js";
import { startMockProveCart } from "./mockProveCart.js";
import { SimulatedDriver, createStagehandDriver, type DemoDriver } from "./drivers.js";

export const MANDATE_FIELDS = {
  user_id: "demo-buyer",
  item_description: "Trail Runner Shoes, size US 10, one pair",
  item_keywords: ["trail", "runner", "shoes"],
  category: "footwear",
  max_total_price: 120,
  currency: "USD",
  max_quantity: 1,
  required_variant: "US 10",
};

export type Scenario = "match" | "fix" | "review";

export const SCENARIO_CHOICES: Record<
  Scenario,
  { variant: string; quantity: number; addWallet?: boolean; blurb: string }
> = {
  match: {
    variant: "US 10",
    quantity: 1,
    blurb: "agent picks exactly what the buyer authorized",
  },
  fix: {
    variant: "US 9",
    quantity: 1,
    blurb: "agent misclicks the size (US 9 instead of US 10)",
  },
  review: {
    variant: "US 10",
    quantity: 1,
    addWallet: true,
    blurb: "agent adds a wallet the buyer never asked for",
  },
};

export async function runScenario(
  scenario: Scenario,
  opts: { live?: boolean; driver?: DemoDriver } = {},
): Promise<{ outcome: string; driver: DemoDriver; attempts?: number }> {
  let client: ProveCartClient;
  let closeMock: (() => void) | undefined;

  if (opts.live) {
    const apiKey = process.env.PROVECART_API_KEY;
    if (!apiKey) throw new Error("PROVECART_LIVE=1 requires PROVECART_API_KEY");
    client = new ProveCartClient({ apiKey });
  } else {
    const mock = await startMockProveCart();
    closeMock = () => mock.server.close();
    client = new ProveCartClient({
      apiKey: "mock-key",
      baseUrl: mock.baseUrl,
    });
  }

  try {
    const mandate = await client.createMandate(MANDATE_FIELDS);
    const driver = opts.driver ?? new SimulatedDriver();
    const choices = SCENARIO_CHOICES[scenario];
    await driver.buildCart(choices);
    const result = await checkBeforeCheckout({
      client,
      mandateId: String(mandate.id),
      hooks: driver,
    });
    return { outcome: result.outcome, attempts: result.attempts, driver };
  } finally {
    closeMock?.();
  }
}

async function main() {
  const scenario = (process.argv[2] ?? "fix") as Scenario;
  if (!(scenario in SCENARIO_CHOICES)) {
    console.error(`unknown scenario "${scenario}" (use match | fix | review)`);
    process.exit(2);
  }
  const live = process.env.PROVECART_LIVE === "1";
  let driver: DemoDriver | undefined;
  if (process.env.STAGEHAND_LIVE === "1") {
    const here = dirname(fileURLToPath(import.meta.url));
    driver = await createStagehandDriver(
      "file://" + join(here, "..", "demo", "demo-store.html"),
    );
  }
  console.log(
    `scenario=${scenario} (${SCENARIO_CHOICES[scenario].blurb}) mode=${live ? "LIVE api.provecart.com" : "mock (127.0.0.1)"}`,
  );
  const { outcome, attempts, driver: used } = await runScenario(scenario, {
    live,
    driver,
  });
  for (const line of used.log) console.log("  " + line);
  console.log(
    `result: outcome=${outcome} checks=${attempts} buyClicks=${used.buyClicks} escalations=${used.escalations.length}`,
  );
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main().catch((err) => {
    console.error(err);
    process.exit(1);
  });
}
