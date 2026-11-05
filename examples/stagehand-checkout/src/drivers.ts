/**
 * Page drivers: the two ways the flow touches the demo store page.
 *
 * SimulatedDriver (default, offline): keeps the same cart state the
 * demo page would hold and logs each step in Stagehand terms
 * (act / extract). It needs no browser, no LLM key and no network,
 * which is why the smoke test can run anywhere.
 *
 * StagehandDriver (opt-in, STAGEHAND_LIVE=1): drives the real
 * demo-store.html through Stagehand v3 — deterministic page.goto
 * and evaluate for state, stagehand.act() for the clicks a real
 * agent would make. It still only ever opens the local demo page.
 */
import type { Cart, Correction } from "./provecart.js";
import type { CheckoutHooks } from "./checkBeforeCheckout.js";

export interface DemoDriver extends CheckoutHooks {
  log: string[];
  buyClicks: number;
  escalations: string[];
  /** Simulate the agent building the cart (its choices may be wrong — that is the point). */
  buildCart: (choices: { variant: string; quantity: number; addWallet?: boolean }) => Promise<void>;
}

const SHOES = {
  name: "Trail Runner Shoes",
  unit_price: 110,
  category: "footwear",
  brand: "Demo",
};
const WALLET = {
  name: "Leather Wallet",
  unit_price: 45,
  category: "accessories",
  brand: "Demo",
};

export class SimulatedDriver implements DemoDriver {
  log: string[] = [];
  buyClicks = 0;
  escalations: string[] = [];
  private items: Cart["items"] = [];

  async buildCart(choices: { variant: string; quantity: number; addWallet?: boolean }) {
    this.log.push(`act("select size ${choices.variant} for the Trail Runner Shoes")`);
    this.log.push(`act("click the Add to cart button")`);
    this.items.push({ ...SHOES, variant: choices.variant, quantity: choices.quantity });
    if (choices.addWallet) {
      this.log.push(`act("click the Add wallet to cart button")`);
      this.items.push({ ...WALLET, variant: "", quantity: 1 });
    }
  }

  async readCart(): Promise<Cart> {
    this.log.push(`extract("the cart items, variants, quantities and total")`);
    const total = this.items.reduce((s, it) => s + it.unit_price * it.quantity, 0);
    return {
      merchant: { name: "Demo Store", domain: "demo.local" },
      items: this.items.map((it) => ({ ...it })),
      total_price: total,
      currency: "USD",
      tax: 0,
      shipping: 0,
      fees: 0,
    };
  }

  async applyCorrection(correction: Correction): Promise<void> {
    const item = this.items.find((it) => it.name === correction.item);
    if (!item) throw new Error(`correction targets unknown item ${correction.item}`);
    if (correction.action === "change_variant") {
      this.log.push(
        `act("change the size of ${item.name} from ${String(correction.from)} to ${String(correction.to)}")`,
      );
      item.variant = String(correction.to);
    } else if (correction.action === "reduce_quantity") {
      this.log.push(
        `act("reduce the quantity of ${item.name} from ${String(correction.from)} to ${String(correction.to)}")`,
      );
      item.quantity = Number(correction.to);
    } else if (correction.action === "remove_item") {
      this.log.push(`act("remove ${item.name} from the cart")`);
      this.items = this.items.filter((it) => it !== item);
    } else {
      throw new Error(`driver cannot apply correction action ${correction.action}`);
    }
  }

  async clickBuy(): Promise<void> {
    this.buyClicks += 1;
    this.log.push(`act("click the Buy button")  <-- only reached after MATCH`);
  }

  async escalate(reason: string, recordId?: string): Promise<void> {
    this.escalations.push(reason);
    this.log.push(`STOP: escalate to buyer (${reason}; record ${recordId ?? "n/a"})`);
  }
}

/**
 * Real Stagehand driver. Imported lazily so the offline path never
 * needs the Stagehand package, a browser, or an LLM key.
 * Stagehand v3 shape: methods live on the instance
 * (stagehand.act/extract), pages come from stagehand.context.
 */
export async function createStagehandDriver(demoPageUrl: string): Promise<DemoDriver> {
  // @ts-ignore optional peer, loaded only in STAGEHAND_LIVE mode
  const { Stagehand } = await import("@browserbasehq/stagehand");
  const stagehand = new Stagehand({
    env: process.env.BROWSERBASE_API_KEY ? "BROWSERBASE" : "LOCAL",
    model: process.env.STAGEHAND_MODEL ?? "openai/gpt-5",
  });
  await stagehand.init();
  const page = stagehand.context.pages()[0];
  await page.goto(demoPageUrl);

  const driver: DemoDriver = {
    log: [],
    buyClicks: 0,
    escalations: [],
    async buildCart(choices) {
      await page.evaluate((v: string) => {
        (document.getElementById("size") as HTMLSelectElement).value = v;
      }, choices.variant);
      await stagehand.act("click the Add to cart button");
      if (choices.addWallet) {
        await stagehand.act("click the Add wallet to cart button");
      }
    },
    async readCart() {
      return page.evaluate(() => (window as any).__readCart());
    },
    async applyCorrection(correction) {
      if (correction.action === "change_variant") {
        await page.evaluate(
          ([name, v]: [string, string]) => (window as any).__setVariant(name, v),
          [String(correction.item ?? ""), String(correction.to)],
        );
      } else if (correction.action === "reduce_quantity") {
        await page.evaluate(
          ([name, q]: [string, number]) => (window as any).__setQuantity(name, q),
          [String(correction.item ?? ""), Number(correction.to)],
        );
      } else {
        throw new Error(`driver cannot apply correction action ${correction.action}`);
      }
    },
    async clickBuy() {
      driver.buyClicks += 1;
      await stagehand.act("click the Buy button");
    },
    async escalate(reason) {
      driver.escalations.push(reason);
    },
  };
  return driver;
}
