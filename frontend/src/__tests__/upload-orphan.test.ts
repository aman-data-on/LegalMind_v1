/**
 * A refused upload leaves nothing behind (2026-10-08). The contract is made first and the
 * document second, so a file the server refuses ("File content does not match a supported
 * format") used to leave an empty contract on the Dashboard — from the Ask page and from
 * the Dashboard's own upload alike. Archived, never deleted: it is reversible.
 */
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, uploadFirstDocument } from "@/lib/api";

function reply(status: number, body: unknown): Response {
  return {
    ok: status < 400, status,
    headers: new Headers({ "X-Request-Id": "req-1", "Content-Type": "application/json" }),
    json: async () => body,
  } as unknown as Response;
}

function stub(responses: Response[]) {
  const calls: { url: string; method: string }[] = [];
  vi.stubGlobal("fetch", async (input: RequestInfo | URL, init?: RequestInit) => {
    calls.push({ url: String(input), method: init?.method ?? "GET" });
    return responses.shift()!;
  });
  return calls;
}

const FILE = new File(["x"], "broken.pdf", { type: "application/pdf" });

afterEach(() => vi.unstubAllGlobals());

describe("uploadFirstDocument", () => {
  it("archives the empty contract when the document is refused, and rethrows the refusal", async () => {
    const calls = stub([
      reply(422, { error: { code: "VALIDATION", message: "File content does not match a supported format.", request_id: "r" } }),
      reply(200, { data: { id: "c-1" } }),
    ]);
    await expect(uploadFirstDocument("c-1", FILE)).rejects.toBeInstanceOf(ApiError);
    expect(calls.map((c) => c.method)).toEqual(["POST", "POST"]);
    expect(calls[0]!.url).toContain("/contracts/c-1/document-versions");
    expect(calls[1]!.url).toContain("/contracts/c-1/archive");
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);          // nothing is destroyed
  });

  it("still reports the refusal when the archive itself is refused", async () => {
    stub([
      reply(422, { error: { code: "VALIDATION", message: "refused", request_id: "r" } }),
      reply(403, { error: { code: "FORBIDDEN", message: "no", request_id: "r" } }),
    ]);
    await expect(uploadFirstDocument("c-2", FILE)).rejects.toMatchObject({ status: 422 });
  });

  it("leaves the contract alone when the failure may have come after the server kept the version", async () => {
    for (const failure of [reply(502, { error: { code: "BAD_GATEWAY", message: "x", request_id: "r" } }),
                           new TypeError("network down")]) {
      const calls: string[] = [];
      vi.stubGlobal("fetch", async (input: RequestInfo | URL) => {
        calls.push(String(input));
        if (failure instanceof Error) throw failure;
        return failure;
      });
      await expect(uploadFirstDocument("c-9", FILE)).rejects.toBeDefined();
      expect(calls).toHaveLength(1);                                       // no archive call
      vi.unstubAllGlobals();
    }
  });

  it("archives nothing when the document is accepted", async () => {
    const calls = stub([reply(201, { data: { document_version: { id: "v-1" } } })]);
    const uploaded = await uploadFirstDocument("c-3", FILE);
    expect(uploaded.document_version.id).toBe("v-1");
    expect(calls).toHaveLength(1);
  });
});
