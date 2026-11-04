/** The one PDF download: 200 the file, 202 wait and ask again (Retry-After), 503
 *  PDF_NOT_MADE a plain message and no more asking, 409 the gate unchanged, ~2 min cap. */
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api";
import { PDF_TIMEOUT, fetchPdf } from "@/lib/pdfDownload";

const reply = (status: number, body: unknown = {}, headers: Record<string, string> = {}) =>
  new Response(status === 200 ? "%PDF" : JSON.stringify(body), { status, headers });

afterEach(() => vi.unstubAllGlobals());

describe("fetchPdf", () => {
  it("returns the file on 200 with its served name", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => reply(200, null, { "Content-Disposition": 'attachment; filename="Reply v3.pdf"' })));
    const got = await fetchPdf("/document-versions/v/reply-pdf");
    expect(got.kind).toBe("file");
    expect(got.kind === "file" && got.name).toBe("Reply v3.pdf");
  });

  it("waits Retry-After on 202 and asks again until the file is made", async () => {
    const fetch = vi.fn()
      .mockResolvedValueOnce(reply(202, { data: { status: "rendering" } }, { "Retry-After": "3" }))
      .mockResolvedValueOnce(reply(202, { data: { status: "rendering" } }, { "Retry-After": "5" }))
      .mockResolvedValueOnce(reply(200));
    vi.stubGlobal("fetch", fetch);
    const slept: number[] = [];
    const onWaiting = vi.fn();
    const got = await fetchPdf("/document-versions/v/pdf", { onWaiting, sleep: async (ms) => { slept.push(ms); } });
    expect(got.kind).toBe("file");
    expect(slept).toEqual([3000, 5000]);
    expect(onWaiting).toHaveBeenCalledTimes(2);
    expect(fetch).toHaveBeenCalledTimes(3);
  });

  it("stops on 503 PDF_NOT_MADE and says the Word file still downloads", async () => {
    const fetch = vi.fn(async () => reply(503, { error: { code: "PDF_NOT_MADE", message: "The PDF could not be made." } }));
    vi.stubGlobal("fetch", fetch);
    const got = await fetchPdf("/document-versions/v/pdf", { sleep: async () => {} });
    expect(got).toEqual({ kind: "not-made", message: "The PDF could not be made. The Word file can still be downloaded." });
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("gives up after about two minutes of rendering", async () => {
    let t = 0;
    vi.stubGlobal("fetch", vi.fn(async () => reply(202, {}, { "Retry-After": "3" })));
    const got = await fetchPdf("/x", { now: () => t, sleep: async (ms) => { t += ms; } });
    expect(got).toEqual({ kind: "timeout", message: PDF_TIMEOUT });
    expect(t).toBeLessThanOrEqual(120_000);
  });

  it("keeps a 409 REPLY_UNDECIDED as the ApiError the gate list reads", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => reply(409, { error: { code: "REPLY_UNDECIDED", message: "Open points." } })));
    await expect(fetchPdf("/x")).rejects.toBeInstanceOf(ApiError);
  });
});
