/**
 * ProveCart pre-action hook for Mastra.
 *
 * Wraps a Mastra tool so the check runs before the wrapped purchase
 * tool executes. The pending order, booking or reservation is read
 * from the tool input, compared with the customer's signed mandate,
 * and the wrapped tool runs only on a MATCH.
 *
 * Verdict routing (same semantics as the shared ProveCart client):
 *   MATCH               -> proceed: run the wrapped tool
 *   BLOCK + known fixes -> do not run it; return a refusal object
 *                          carrying the corrections, so the agent can
 *                          apply only fixes inside the customer's
 *                          existing authorization and re-check
 *   BLOCK otherwise,
 *   REVIEW, unknown     -> do not run it; return a refusal object
 *                          that escalates to the customer
 *
 * The client is injected and duck-typed. No network call happens on
 * import.
 */

export type CheckKind = "cart" | "booking" | "reservation";
export type Decision = "proceed" | "fix" | "escalate";

export interface Correction {
  action?: string;
  [key: string]: unknown;
}

export interface CheckResponse {
  verdict?: string;
  corrections?: Correction[];
  record_id?: string;
  max_attempts?: number;
  [key: string]: unknown;
}

export interface ProveCartClient {
  check_cart?: (payload: Record<string, unknown>) => Promise<CheckResponse> | CheckResponse;
  check_booking?: (payload: Record<string, unknown>) => Promise<CheckResponse> | CheckResponse;
  check_reservation?: (payload: Record<string, unknown>) => Promise<CheckResponse> | CheckResponse;
  /** Older cart-only shape, adapted for cart checks. */
  verify_cart?: (payload: Record<string, unknown>) => Promise<CheckResponse> | CheckResponse;
  route_verdict?: (
    response: CheckResponse,
  ) => [Decision, Record<string, unknown>] | { decision: Decision; detail: Record<string, unknown> };
}

export const KNOWN_ACTIONS = new Set<string>([
  "remove_item", "replace_item", "change_variant", "reduce_quantity",
  "reduce_total", "change_currency", "correct_traveler_name",
  "change_airport", "change_travel_date", "change_departure_time",
  "add_itinerary", "rebuild_itinerary", "change_cabin",
  "change_fare_terms", "add_hotel_stay", "change_room",
  "change_provider", "change_location", "change_date", "change_time",
  "change_party_size", "correct_reservation_name", "reduce_deposit",
  "change_cancellation_terms",
]);

export function routeVerdict(
  response: CheckResponse,
): { decision: Decision; detail: Record<string, unknown> } {
  const verdict = response?.verdict;
  if (verdict === "MATCH") {
    return { decision: "proceed", detail: { record_id: response.record_id } };
  }
  if (verdict === "BLOCK") {
    const corrections = response.corrections ?? [];
    if (
      corrections.length > 0 &&
      corrections.every((c) => typeof c?.action === "string" && KNOWN_ACTIONS.has(c.action))
    ) {
      return {
        decision: "fix",
        detail: {
          corrections,
          record_id: response.record_id,
          max_attempts: response.max_attempts,
        },
      };
    }
    return {
      decision: "escalate",
      detail: { reason: "BLOCK without usable corrections", record_id: response.record_id },
    };
  }
  return {
    decision: "escalate",
    detail: { reason: `verdict ${verdict} needs the buyer`, record_id: response?.record_id },
  };
}

export interface ProveCartRefusal {
  provecart_blocked: true;
  provecart_decision: Decision;
  verdict: string | undefined;
  check_kind: CheckKind;
  corrections: Correction[];
  record_id: string | undefined;
  max_attempts: number | undefined;
  detail: Record<string, unknown>;
  error: string;
}

export interface WrapOptions {
  client: ProveCartClient;
  /** Which check to run. Default: "cart". */
  kind?: CheckKind;
  /** Map tool input -> check payload. Default: unwrap a nested
   *  cart / booking / reservation object, else use the input as-is. */
  extractor?: (kind: CheckKind, input: Record<string, unknown>) => Record<string, unknown>;
}

const CHECK_METHOD: Record<CheckKind, "check_cart" | "check_booking" | "check_reservation"> = {
  cart: "check_cart",
  booking: "check_booking",
  reservation: "check_reservation",
};

function defaultExtractor(kind: CheckKind, input: Record<string, unknown>) {
  const nested = input?.[kind];
  if (nested && typeof nested === "object" && !Array.isArray(nested)) {
    const payload: Record<string, unknown> = { ...(nested as Record<string, unknown>) };
    for (const key of ["mandate_id", "previous_record_id"]) {
      if (key in input && !(key in payload)) payload[key] = input[key];
    }
    return payload;
  }
  return { ...(input ?? {}) };
}

function refusal(
  kind: CheckKind,
  response: CheckResponse | null,
  decision: Decision,
  detail: Record<string, unknown>,
): ProveCartRefusal {
  return {
    provecart_blocked: true,
    provecart_decision: decision,
    verdict: response?.verdict,
    check_kind: kind,
    corrections: response?.corrections ?? (detail.corrections as Correction[] | undefined) ?? [],
    record_id: response?.record_id ?? (detail.record_id as string | undefined),
    max_attempts: response?.max_attempts ?? (detail.max_attempts as number | undefined),
    detail,
    error:
      "ProveCart check did not return MATCH, so the purchase tool was not run. " +
      "On 'fix', apply only the listed corrections inside the customer's existing " +
      "authorization and re-check with previous_record_id. On 'escalate', stop and " +
      "ask the customer.",
  };
}

/** Run one check and route it. Returns a refusal, or null to proceed. */
export async function checkBeforeTool(
  options: WrapOptions,
  input: Record<string, unknown>,
): Promise<ProveCartRefusal | null> {
  const kind = options.kind ?? "cart";
  const payload = (options.extractor ?? defaultExtractor)(kind, input ?? {});
  let response: CheckResponse;
  try {
    const method = options.client[CHECK_METHOD[kind]];
    if (typeof method === "function") {
      response = await method.call(options.client, payload);
    } else if (kind === "cart" && typeof options.client.verify_cart === "function") {
      response = await options.client.verify_cart(payload);
    } else {
      throw new TypeError(`client does not provide ${CHECK_METHOD[kind]}()`);
    }
  } catch (err) {
    // A failed check never lets a purchase through.
    return refusal(kind, null, "escalate", { reason: `check failed: ${String(err)}` });
  }
  let decision: Decision;
  let detail: Record<string, unknown>;
  if (typeof options.client.route_verdict === "function") {
    const routed = options.client.route_verdict(response);
    if (Array.isArray(routed)) {
      [decision, detail] = routed;
    } else {
      ({ decision, detail } = routed);
    }
  } else {
    ({ decision, detail } = routeVerdict(response));
  }
  if (decision === "proceed") return null;
  return refusal(kind, response, decision, detail);
}

/** Minimal structural shape of a Mastra tool (createTool output). */
export interface MastraLikeTool<I = any, O = any> {
  id: string;
  description?: string;
  execute: (input: I, context?: unknown) => Promise<O>;
  [key: string]: unknown;
}

/**
 * Wrap a Mastra tool so the ProveCart check runs first.
 *
 * Works with a real tool built by `createTool` from `@mastra/core`
 * and with any object carrying `id` and `execute`. The returned
 * tool keeps the original id, description and schemas; only its
 * `execute` gains the pre-action check. On a non-proceed verdict
 * the wrapped execute is never called and the refusal object is
 * returned as the tool result.
 */
export function wrapMastraTool<I extends Record<string, unknown>, O>(
  tool: MastraLikeTool<I, O>,
  options: WrapOptions,
): MastraLikeTool<I, O | ProveCartRefusal> {
  if (!tool || typeof tool.execute !== "function") {
    throw new TypeError("wrapMastraTool expects a tool with an execute function");
  }
  const original = tool.execute.bind(tool);
  return {
    ...tool,
    execute: async (input: I, context?: unknown) => {
      const blocked = await checkBeforeTool(options, input as Record<string, unknown>);
      if (blocked) return blocked;
      return original(input, context);
    },
  };
}

/** Function-level form: wrap any execute function the same way. */
export function withProveCartCheck<A extends Record<string, unknown>, R>(
  execute: (input: A, context?: unknown) => Promise<R>,
  options: WrapOptions,
): (input: A, context?: unknown) => Promise<R | ProveCartRefusal> {
  return async (input: A, context?: unknown) => {
    const blocked = await checkBeforeTool(options, input);
    if (blocked) return blocked;
    return execute(input, context);
  };
}

/** Offline fake client for examples and tests. No network, ever. */
export class FakeProveCartClient implements ProveCartClient {
  calls: Array<{ kind: CheckKind; payload: Record<string, unknown> }> = [];
  constructor(
    private response: CheckResponse | ((payload: Record<string, unknown>) => CheckResponse) = {
      verdict: "MATCH",
      corrections: [],
      record_id: "rec_mock_1",
      max_attempts: 3,
    },
  ) {}
  private handle(kind: CheckKind, payload: Record<string, unknown>): CheckResponse {
    this.calls.push({ kind, payload });
    return typeof this.response === "function" ? this.response(payload) : { ...this.response };
  }
  check_cart(payload: Record<string, unknown>) { return this.handle("cart", payload); }
  check_booking(payload: Record<string, unknown>) { return this.handle("booking", payload); }
  check_reservation(payload: Record<string, unknown>) { return this.handle("reservation", payload); }
  // Deliberately no route_verdict: exercises this module's routing.
}
