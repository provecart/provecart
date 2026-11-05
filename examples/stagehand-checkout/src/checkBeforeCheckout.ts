/**
 * checkBeforeCheckout — the interlock.
 *
 * The one load-bearing safety step for a browser shopping agent:
 *
 *   build cart -> checkBeforeCheckout -> MATCH -> click buy
 *
 * The buy action runs ONLY after a MATCH in the same run. On BLOCK,
 * only corrections that stay inside the buyer's existing
 * authorization are applied, and the cart is re-checked carrying
 * previous_record_id. On REVIEW (or anything unrecognized) the flow
 * stops and escalates to the buyer — it never guesses and never
 * widens the authorization.
 */
import {
  ProveCartClient,
  routeVerdict,
  type Cart,
  type Correction,
} from "./provecart.js";

export interface CheckoutHooks {
  /** Read the cart as it currently stands on the page. */
  readCart: () => Promise<Cart>;
  /**
   * Apply ONE correction to the page cart (e.g. change a size
   * variant, reduce a quantity). Must only move the cart INTO the
   * buyer's existing authorization — the corrections ProveCart
   * returns already satisfy that; do not invent your own.
   */
  applyCorrection: (correction: Correction) => Promise<void>;
  /** The buy click. Called at most once, only after MATCH. */
  clickBuy: () => Promise<void>;
  /** Called when the flow stops for the buyer (REVIEW / dead end). */
  escalate: (reason: string, recordId?: string) => Promise<void>;
}

export type CheckoutOutcome =
  | { outcome: "purchased"; recordId?: string; attempts: number }
  | { outcome: "escalated"; reason: string; recordId?: string; attempts: number };

export async function checkBeforeCheckout(args: {
  client: ProveCartClient;
  mandateId: string;
  hooks: CheckoutHooks;
}): Promise<CheckoutOutcome> {
  const { client, mandateId, hooks } = args;
  let previousRecordId: string | undefined;
  let attempts = 0;
  let maxAttempts = 3;

  for (;;) {
    const cart = await hooks.readCart();
    const response = await client.verifyCart({
      mandateId,
      cart,
      previousRecordId,
      cartChanged: attempts > 0,
    });
    attempts += 1;
    if (typeof response.max_attempts === "number") {
      maxAttempts = response.max_attempts;
    }
    const route = routeVerdict(response);

    if (route.decision === "proceed") {
      await hooks.clickBuy();
      return { outcome: "purchased", recordId: route.recordId, attempts };
    }

    if (route.decision === "fix") {
      if (attempts >= maxAttempts) {
        const reason = `correction budget exhausted after ${attempts} checks`;
        await hooks.escalate(reason, route.recordId);
        return { outcome: "escalated", reason, recordId: route.recordId, attempts };
      }
      for (const correction of route.corrections) {
        await hooks.applyCorrection(correction);
      }
      previousRecordId = route.recordId;
      continue;
    }

    await hooks.escalate(route.reason, route.recordId);
    return {
      outcome: "escalated",
      reason: route.reason,
      recordId: route.recordId,
      attempts,
    };
  }
}
