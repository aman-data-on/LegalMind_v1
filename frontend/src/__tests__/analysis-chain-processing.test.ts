/**
 * The in-flow analysis chain vs a still-processing document (deferred OCR,
 * 2026-09-03).
 *
 * A document whose OCR runs in the background has NO evidence at upload time.
 * If the chain created the Review and fired the analysis anyway, the server
 * would refuse it ("still being processed") — or worse, an unguarded engine
 * would evaluate zero rows and mint MISSING findings against text that is
 * still being recovered. The chain therefore checks the version's own
 * processing status and steps aside; the workspace watches the version and
 * runs the same chain when processing concludes.
 *
 * Pinned here: the skip is BEFORE any write. No Review is created, nothing is
 * analysed, and the skip is keyed on the server's own `processing_status` —
 * never on a client-side guess about how long OCR takes.
 */

import { afterEach, describe, expect, it, vi } from "vitest";

import { chainAnalysis } from "@/lib/analysisChain";
import { api } from "@/lib/api";

function arrange(processingStatus: string) {
  vi.spyOn(api, "snapshots").mockResolvedValue({
    items: [{ id: "snap-1" }] as never,
    page: 1, page_size: 1, total: 1,
  } as never);
  vi.spyOn(api, "contract").mockResolvedValue({
    id: "c1",
    document_versions: [{ id: "v1", version_number: 1 }],
  } as never);
  vi.spyOn(api, "documentVersion").mockResolvedValue({
    id: "v1", processing_status: processingStatus,
  } as never);
  const createReview = vi.spyOn(api, "createReview")
    .mockResolvedValue({ id: "r1" } as never);
  const analyze = vi.spyOn(api, "analyzeReview")
    .mockResolvedValue({ mode: "inline" } as never);
  return { createReview, analyze };
}

afterEach(() => vi.restoreAllMocks());

describe("chainAnalysis and the deferred-OCR gap", () => {
  it("steps aside while the document is PROCESSING — no Review, no analysis", async () => {
    const { createReview, analyze } = arrange("PROCESSING");
    await chainAnalysis("c1", true);
    expect(createReview).not.toHaveBeenCalled();
    expect(analyze).not.toHaveBeenCalled();
  });

  it("runs exactly as before once processing is COMPLETED", async () => {
    const { createReview, analyze } = arrange("COMPLETED");
    await chainAnalysis("c1", true);
    expect(createReview).toHaveBeenCalledWith("v1", "snap-1");
    expect(analyze).toHaveBeenCalledWith("r1");
  });

  it("a FAILED extraction still gets its Review and the honest ANALYSIS_FAILED surface — only the in-between states skip", async () => {
    const { createReview, analyze } = arrange("FAILED");
    await chainAnalysis("c1", true);
    expect(createReview).toHaveBeenCalledWith("v1", "snap-1");
    expect(analyze).toHaveBeenCalledWith("r1");
  });
});
