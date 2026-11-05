// Mock / offline example for provecart-mastra.
//
// Runs with no network and no API key. The default is MOCK mode: an
// injected FakeProveCartClient answers the checks. Live mode is an
// explicit opt-in: set PROVECART_LIVE=1 and pass your own real
// client object where marked below; nothing live runs by default.
//
//   npm run build && node examples/mock-example.mjs
import { FakeProveCartClient, wrapMastraTool } from "../dist/index.js";

if (process.env.PROVECART_LIVE === "1") {
  throw new Error(
    "Live mode is explicit opt-in: construct your real ProveCart client " +
    "here and pass it to wrapMastraTool. This example ships with no live " +
    "client and makes no network calls.",
  );
}

// A stand-in for a tool built with createTool from @mastra/core:
// same shape (id, description, execute), no framework needed offline.
function demoPurchaseTool() {
  return {
    id: "place_order",
    description: "Place the order and take payment.",
    execute: async (input) => ({ placed: true, total_price: input.total_price }),
  };
}

const scenarios = [
  { verdict: "MATCH", corrections: [], record_id: "rec_1", max_attempts: 3 },
  { verdict: "BLOCK", corrections: [{ action: "remove_item" }], record_id: "rec_2", max_attempts: 3 },
  { verdict: "REVIEW", corrections: [], record_id: "rec_3", max_attempts: 3 },
];
const input = {
  mandate_id: "mandate_demo",
  merchant: { name: "Demo Shop" },
  items: [{ name: "Demo item", quantity: 1 }],
  total_price: 42,
};

for (const response of scenarios) {
  const tool = wrapMastraTool(demoPurchaseTool(), {
    client: new FakeProveCartClient(response),
    kind: "cart",
  });
  const out = await tool.execute(input);
  if (out.provecart_blocked) {
    console.log(`${response.verdict}: tool skipped - decision=${out.provecart_decision}, corrections=${JSON.stringify(out.corrections)}`);
  } else {
    console.log(`${response.verdict}: proceed - the purchase tool ran`);
  }
}
