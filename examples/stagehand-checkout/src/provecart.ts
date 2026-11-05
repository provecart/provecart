/**
 * ProveCart client + verdict routing (TypeScript port).
 *
 * Vendored, self-contained port of the reference client semantics
 * (ACF v0.2, com.provecart.conformity), so this example runs without
 * any other ProveCart package installed. When the packaged client
 * ships for TypeScript, this file is the part you would delete.
 *
 * Consumer rules:
 *   MATCH             -> proceed to payment.
 *   BLOCK + fixes     -> apply ONLY repairs that bring the cart INTO
 *                        the buyer's existing authorization, then
 *                        resubmit as a new check carrying
 *                        previous_record_id, within max_attempts.
 *   REVIEW / unknown  -> stop and escalate to the buyer. Never guess,
 *   action               never widen the authorization.
 *
 * API contract (https://api.provecart.com, X-API-Key header):
 *   POST /mandates  {user_id, item_description, item_keywords,
 *                    category, max_total_price, currency,
 *                    max_quantity, expires_at, ...} -> signed mandate
 *   POST /verify    {mandate_id, merchant{name, domain},
 *                    items[{name, variant, quantity, unit_price,
 *                    category, brand}], total_price, currency, tax,
 *                    shipping, fees, previous_record_id?,
 *                    cart_changed?}
 *                   -> {verdict, corrections[], max_attempts,
 *                       record_id, verdict_token, ...}
 */

export interface CartItem {
  name: string;
  variant?: string;
  quantity: number;
  unit_price: number;
  category?: string;
  brand?: string;
}

export interface Cart {
  merchant: { name: string; domain: string };
  items: CartItem[];
  total_price: number;
  currency?: string;
  tax?: number;
  shipping?: number;
  fees?: number;
}

export interface Correction {
  action: string;
  item?: string;
  field?: string;
  from?: unknown;
  to?: unknown;
  [key: string]: unknown;
}

export interface VerifyResponse {
  verdict: "MATCH" | "BLOCK" | "REVIEW" | string;
  corrections?: Correction[];
  max_attempts?: number;
  record_id?: string;
  verdict_token?: string;
  [key: string]: unknown;
}

export const KNOWN_ACTIONS = new Set([
  "remove_item", "replace_item", "change_variant", "reduce_quantity",
  "reduce_total", "change_currency", "correct_traveler_name",
  "change_airport", "change_travel_date", "change_departure_time",
  "add_itinerary", "rebuild_itinerary", "change_cabin",
  "change_fare_terms", "add_hotel_stay", "change_room",
  "change_provider", "change_location", "change_date", "change_time",
  "change_party_size", "correct_reservation_name", "reduce_deposit",
  "change_cancellation_terms",
]);

export type Transport = (
  path: string,
  body: Record<string, unknown>,
) => Promise<{ status: number; json: Record<string, unknown> }>;

export class ProveCartClient {
  private apiKey: string;
  private base: string;
  private transport?: Transport;

  constructor(opts: {
    apiKey: string;
    baseUrl?: string;
    transport?: Transport;
  }) {
    this.apiKey = opts.apiKey;
    this.base = (opts.baseUrl ?? "https://api.provecart.com").replace(/\/$/, "");
    this.transport = opts.transport;
  }

  private async post(
    path: string,
    body: Record<string, unknown>,
  ): Promise<Record<string, unknown>> {
    if (this.transport) {
      const { status, json } = await this.transport(path, body);
      if (status !== 200) {
        throw new Error(`ProveCart ${path} failed: ${status} ${JSON.stringify(json)}`);
      }
      return json;
    }
    const res = await fetch(this.base + path, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": this.apiKey,
      },
      body: JSON.stringify(body),
    });
    const json = (await res.json().catch(() => ({}))) as Record<string, unknown>;
    if (res.status !== 200) {
      throw new Error(`ProveCart ${path} failed: ${res.status} ${JSON.stringify(json)}`);
    }
    return json;
  }

  async createMandate(fields: Record<string, unknown>): Promise<Record<string, unknown>> {
    return this.post("/mandates", fields);
  }

  async verifyCart(args: {
    mandateId: string;
    cart: Cart;
    previousRecordId?: string;
    cartChanged?: boolean;
  }): Promise<VerifyResponse> {
    const { cart } = args;
    const body: Record<string, unknown> = {
      mandate_id: args.mandateId,
      merchant: cart.merchant,
      items: cart.items,
      total_price: cart.total_price,
      currency: cart.currency ?? "USD",
      tax: cart.tax ?? 0,
      shipping: cart.shipping ?? 0,
      fees: cart.fees ?? 0,
      cart_changed: args.cartChanged ?? false,
    };
    if (args.previousRecordId) body.previous_record_id = args.previousRecordId;
    return (await this.post("/verify", body)) as unknown as VerifyResponse;
  }
}

export type RouteDecision =
  | { decision: "proceed"; recordId?: string }
  | { decision: "fix"; corrections: Correction[]; recordId?: string; maxAttempts?: number }
  | { decision: "escalate"; reason: string; recordId?: string };

/**
 * Route a verdict. "fix" is returned only when every correction is a
 * known action; anything else escalates to the buyer.
 */
export function routeVerdict(response: VerifyResponse): RouteDecision {
  const verdict = response.verdict;
  if (verdict === "MATCH") {
    return { decision: "proceed", recordId: response.record_id };
  }
  if (verdict === "BLOCK") {
    const corrections = response.corrections ?? [];
    if (
      corrections.length > 0 &&
      corrections.every((c) => KNOWN_ACTIONS.has(c.action))
    ) {
      return {
        decision: "fix",
        corrections,
        recordId: response.record_id,
        maxAttempts: response.max_attempts,
      };
    }
    return {
      decision: "escalate",
      reason: "BLOCK without usable corrections",
      recordId: response.record_id,
    };
  }
  return {
    decision: "escalate",
    reason: `verdict ${verdict} needs the buyer`,
    recordId: response.record_id,
  };
}
