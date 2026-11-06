/** Item 3 (UI review, 2026-11-06): a finding's explanation is asked for once, however
 *  many cards ask at once, and a FAILED answer is asked again later. */
import { beforeEach, describe, expect, it, vi } from "vitest";

const explainFinding = vi.fn();
vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  api: { explainFinding: (id: string) => explainFinding(id) },
}));

import { explanationFor } from "@/components/workspace/FindingsPane";

describe("explanationFor", () => {
  beforeEach(() => explainFinding.mockReset());

  it("asks the server once for concurrent cards, then answers from the cache", async () => {
    explainFinding.mockResolvedValue({ status: "ACCEPTED", text: "Plain words." });
    const [a, b] = await Promise.all([explanationFor("f1"), explanationFor("f1")]);
    expect(a).toBe(b);
    await explanationFor("f1");
    expect(explainFinding).toHaveBeenCalledTimes(1);
  });

  it("does not keep a FAILED answer", async () => {
    explainFinding.mockResolvedValue({ status: "FAILED", text: null });
    await explanationFor("f2");
    await explanationFor("f2");
    expect(explainFinding).toHaveBeenCalledTimes(2);
  });
});
