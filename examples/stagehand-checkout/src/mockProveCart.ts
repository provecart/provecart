/**
 * A local fake ProveCart verdict server for offline runs.
 *
 * It implements the same wire contract as the real API
 * (POST /mandates, POST /verify -> {verdict, corrections[],
 * max_attempts, record_id}) with a small deterministic rule set
 * over the mandate the caller created:
 *
 *   - an item whose name shares no keyword with the mandate, or
 *     whose category differs from the mandate category -> REVIEW
 *     (the check cannot confirm this is what the buyer asked for)
 *   - variant differs from the mandate's required_variant
 *     -> BLOCK with a change_variant correction
 *   - quantity above max_quantity -> BLOCK with reduce_quantity
 *   - total above max_total_price -> BLOCK with reduce_quantity
 *     when that brings the total back inside the limit
 *   - otherwise -> MATCH
 *
 * It listens on 127.0.0.1 only and is never a real merchant or a
 * real ProveCart deployment. Live mode (PROVECART_LIVE=1) points
 * the client at https://api.provecart.com instead and this server
 * is not started.
 */
import { createServer, type Server } from "node:http";
import type { CartItem, VerifyResponse } from "./provecart.js";

interface Mandate {
  id: string;
  item_keywords: string[];
  category?: string;
  max_total_price?: number;
  max_quantity?: number;
  required_variant?: string;
}

const mandates = new Map<string, Mandate>();
let mandateSeq = 0;
let recordSeq = 0;

export function evaluate(mandate: Mandate, body: Record<string, unknown>): VerifyResponse {
  recordSeq += 1;
  const record_id = `rec_mock_${recordSeq}`;
  const items = (body.items ?? []) as CartItem[];
  const total = Number(body.total_price ?? 0);
  const base = { record_id, max_attempts: 3, verdict_token: `vt_${record_id}` };

  const offMandate = items.find((it) => {
    const name = it.name.toLowerCase();
    const keywordHit = mandate.item_keywords.some((k) =>
      name.includes(k.toLowerCase()),
    );
    const categoryHit =
      !mandate.category || !it.category || it.category === mandate.category;
    return !keywordHit || !categoryHit;
  });
  if (offMandate) {
    return {
      ...base,
      verdict: "REVIEW",
      corrections: [],
      reasons: [`"${offMandate.name}" is outside the buyer's mandate`],
    };
  }

  for (const it of items) {
    if (
      mandate.required_variant &&
      it.variant &&
      it.variant !== mandate.required_variant
    ) {
      return {
        ...base,
        verdict: "BLOCK",
        corrections: [
          {
            action: "change_variant",
            item: it.name,
            field: "variant",
            from: it.variant,
            to: mandate.required_variant,
          },
        ],
        reasons: [`variant ${it.variant} != authorized ${mandate.required_variant}`],
      };
    }
    if (mandate.max_quantity && it.quantity > mandate.max_quantity) {
      return {
        ...base,
        verdict: "BLOCK",
        corrections: [
          {
            action: "reduce_quantity",
            item: it.name,
            field: "quantity",
            from: it.quantity,
            to: mandate.max_quantity,
          },
        ],
        reasons: [`quantity ${it.quantity} > authorized ${mandate.max_quantity}`],
      };
    }
  }

  if (mandate.max_total_price && total > mandate.max_total_price) {
    const first = items[0];
    if (first && first.quantity > 1) {
      return {
        ...base,
        verdict: "BLOCK",
        corrections: [
          {
            action: "reduce_quantity",
            item: first.name,
            field: "quantity",
            from: first.quantity,
            to: first.quantity - 1,
          },
        ],
        reasons: [`total ${total} > authorized ${mandate.max_total_price}`],
      };
    }
    return {
      ...base,
      verdict: "REVIEW",
      corrections: [],
      reasons: [`total ${total} exceeds the authorized ${mandate.max_total_price} with no in-authorization repair`],
    };
  }

  return { ...base, verdict: "MATCH", corrections: [] };
}

export function handlePost(
  path: string,
  body: Record<string, unknown>,
): { status: number; json: Record<string, unknown> } {
  if (path === "/mandates") {
    mandateSeq += 1;
    const mandate: Mandate = {
      id: `mand_mock_${mandateSeq}`,
      item_keywords: (body.item_keywords as string[]) ?? [],
      category: body.category as string | undefined,
      max_total_price: body.max_total_price as number | undefined,
      max_quantity: body.max_quantity as number | undefined,
      required_variant: body.required_variant as string | undefined,
    };
    mandates.set(mandate.id, mandate);
    return { status: 200, json: { id: mandate.id, status: "signed" } };
  }
  if (path === "/verify") {
    const mandate = mandates.get(String(body.mandate_id));
    if (!mandate) {
      return { status: 404, json: { error: "unknown mandate_id" } };
    }
    return {
      status: 200,
      json: evaluate(mandate, body) as unknown as Record<string, unknown>,
    };
  }
  return { status: 404, json: { error: `unknown path ${path}` } };
}

export async function startMockProveCart(): Promise<{
  server: Server;
  baseUrl: string;
}> {
  const server = createServer((req, res) => {
    const chunks: Buffer[] = [];
    req.on("data", (c) => chunks.push(c as Buffer));
    req.on("end", () => {
      try {
        const body = JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}");
        const { status, json } = handlePost(req.url ?? "", body);
        res.writeHead(status, { "Content-Type": "application/json" });
        res.end(JSON.stringify(json));
      } catch (err) {
        res.writeHead(400, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: String(err) }));
      }
    });
  });
  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const addr = server.address();
  const port = typeof addr === "object" && addr ? addr.port : 0;
  return { server, baseUrl: `http://127.0.0.1:${port}` };
}
