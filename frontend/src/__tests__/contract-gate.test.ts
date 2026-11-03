/**
 * AM-245 — the "is this a contract?" gate. The server decides and records; the screen
 * only asks again with an explicit, audited override. Pinned here: "Review anyway"
 * sends `review_anyway=true`, and an ordinary analysis never does.
 */
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";

function stubFetch() {
  const calls: string[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    calls.push(String(input));
    return new Response(JSON.stringify({ data: { review_id: "r1", review_status: "DRAFT",
      not_a_contract: true } }), { status: 200, headers: { "content-type": "application/json" } });
  }));
  return calls;
}

afterEach(() => vi.unstubAllGlobals());

describe("the contract gate's override", () => {
  it("is sent only when the reader chooses Review anyway", async () => {
    const calls = stubFetch();
    const refused = await api.analyzeReview("r1");
    await api.analyzeReview("r1", undefined, true);
    expect(refused.not_a_contract).toBe(true);
    expect(calls[0]).not.toContain("review_anyway");
    expect(calls[1]).toContain("review_anyway=true");
  });
});
