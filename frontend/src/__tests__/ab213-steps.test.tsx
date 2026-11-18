/** AB-213 PR 2: one owner, one main button per stage (D1, D5, D6, D7). */
import { afterEach, describe, expect, it, vi } from "vitest";

import { stageLine } from "@/lib/labels";
import { nextStep } from "@/lib/nextStep";

const base = { viewer: "owner" as const, canAnswer: true };

describe("AB-213 stage steps", () => {
  it("D1: a deal on hold is never stuck — our reply (with the question) is next", () => {
    expect(nextStep({ ...base, stage: "ON_HOLD" })?.kind).toBe("prepareReply");
    expect(nextStep({ ...base, stage: "ON_HOLD", replyReady: true })?.kind).toBe("sendReply");
    expect(nextStep({ ...base, stage: "ON_HOLD", finalLatest: true })).toBeNull();
    expect(nextStep({ viewer: "legal", canAnswer: true, stage: "ON_HOLD" })).toBeNull();
  });
  it("D5: at Final nobody has a header button; Legal never has a main one", () => {
    expect(nextStep({ ...base, stage: "FINAL" })).toBeNull();
    expect(nextStep({ viewer: "legal", canAnswer: false, stage: "FINAL" })).toBeNull();
  });
  it("D6: a final contract not yet with Legal is not called 'with Legal'", () => {
    expect(stageLine("INTERNAL_REVIEW", { sent_to_legal: false }, "owner", true)).toBe("Final contract, not sent to Legal");
    expect(stageLine("INTERNAL_REVIEW", { sent_to_legal: true }, "owner", true)).toBe("Final contract, with Legal");
  });
});

describe("D7: the API client", () => {
  afterEach(() => { vi.unstubAllGlobals(); vi.resetModules(); });
  it("shares one call between identical GETs in flight", async () => {
    const calls: string[] = [];
    vi.stubGlobal("fetch", vi.fn(async (u: string) => {
      calls.push(String(u));
      return new Response(JSON.stringify({ data: { ok: 1 } }),
                          { status: 200, headers: { "Content-Type": "application/json" } });
    }));
    const { api } = await import("@/lib/api");
    await Promise.all([api.reviewOutcome("r1"), api.reviewOutcome("r1")]);
    expect(calls.filter((c) => c.includes("/reviews/r1/outcome"))).toHaveLength(1);
    await api.reviewOutcome("r1");                       // in flight no more: a fresh read
    expect(calls.filter((c) => c.includes("/reviews/r1/outcome"))).toHaveLength(2);
  });
});
