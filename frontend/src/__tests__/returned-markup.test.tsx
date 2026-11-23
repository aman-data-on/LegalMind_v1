/**
 * Batch 5 (AB-221): "Our contract came back marked up". The chooser's third start, the
 * page's order of uploads and its refusals, one run per click, the landing, and the
 * Changes tab when only the client's tracked changes are compared. Synthetic files only.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const session = { can: (_p: string) => true };
vi.mock("@/lib/session", () => ({ useSession: () => session }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }), useSearchParams: () => new URLSearchParams() }));
// the dialog's portal needs a browser; its content is what is asserted here
vi.mock("@/components/Dialog", () => ({ Dialog: ({ children }: { children: React.ReactNode }) => <div>{children}</div> }));
vi.mock("@/lib/analysisChain", () => ({ chainAnalysis: vi.fn(async () => undefined), analyseVersion: vi.fn() }));

import { NewContractChooser } from "@/components/newcontract/NewContractChooser";
import { BaseChoice, ReturnedFile, ReturnedMarkup } from "@/components/newcontract/ReturnedMarkup";
import ReturnedMarkupPage from "@/app/contracts/new/returned/page";
import { ChangesBanners } from "@/components/workspace/ChangesBanners";
import { contractHref } from "@/components/workspace/model";
import { api, ApiError } from "@/lib/api";
import { actionsFor, oursLabel, type ChangeList, type ClientChange } from "@/lib/changes";
import { RETURNED_COPY as C } from "@/lib/labels";
import { convertOffered } from "@/lib/package";
import {
  afterRefusal, copyRefusal, dealsShown, fileRefusal, missingOf, NEW_DEAL, openForReturn, refusalOf, sendReturned,
  singleFlight, type Made,
} from "@/lib/returned";
import type { Contract } from "@/lib/types";
import { sameFile } from "@/lib/upload";

const docx = (name = "back.docx", body = "theirs") => new File([body], name);
const RETURNED = docx("msa-returned.docx", "returned");
const COPY = docx("msa-sent.docx", "sent");

let uploads: unknown[][] = [];
beforeEach(() => {
  uploads = [];
  session.can = () => true;
  vi.spyOn(api, "createContract").mockResolvedValue({ id: "c-new" } as Contract);
  vi.spyOn(api, "suggestType").mockResolvedValue({ confident: false, suggested_type: null } as never);
  vi.spyOn(api, "uploadDocument").mockImplementation(async (...args: unknown[]) => {
    uploads.push(args);
    return { document_version: { id: `v${uploads.length}` }, duplicate_of: null } as never;
  });
});
afterEach(() => vi.restoreAllMocks());

describe("the start", () => {
  it("the chooser lists three starts; the new one opens the returned-markup page", () => {
    const html = renderToStaticMarkup(<NewContractChooser onUpload={() => undefined} onClose={() => undefined} />);
    expect(html.match(/class="nc-item__l1"/g)).toHaveLength(3);
    expect(html).toContain(`href="/contracts/new/returned"`);
    expect(html).toContain(C.choose);
    expect(html).toContain(C.uploadLine);
  });

  it("the start is absent without contract.create and document.upload (N8)", () => {
    session.can = (p: string) => p !== "document.upload";
    expect(renderToStaticMarkup(<NewContractChooser onUpload={() => undefined} onClose={() => undefined} />))
      .not.toContain("/contracts/new/returned");
    expect(renderToStaticMarkup(<ReturnedMarkupPage />)).not.toContain(C.title);
  });

  it("Upload and compare stays disabled until a client, a deal choice and a file are set", () => {
    const html = renderToStaticMarkup(<ReturnedMarkup />);
    // UI 8: focusable, its reason read with it (aria-disabled, never a silent disabled)
    expect(html).toMatch(/<button type="button" class="ws-btn ws-btn--primary" aria-disabled="true" aria-describedby="rm-bar-why">Upload and compare/);
    expect(html).toContain(`id="rm-bar-why">${C.missing.client}`);
    expect(html).toContain(C.missing.client);
    const f = RETURNED;
    expect(missingOf({ client: null, deal: null, file: null, haveCopy: true, copy: null })).toBe("client");
    expect(missingOf({ client: {}, deal: null, file: null, haveCopy: true, copy: null })).toBe("deal");
    expect(missingOf({ client: {}, deal: "c1", file: null, haveCopy: true, copy: null })).toBe("file");
    expect(missingOf({ client: {}, deal: NEW_DEAL, file: f, haveCopy: true, copy: null })).toBe("copy");
    expect(missingOf({ client: {}, deal: NEW_DEAL, file: f, haveCopy: false, copy: null })).toBeNull();
    expect(missingOf({ client: {}, deal: "c1", file: f, haveCopy: true, copy: null })).toBeNull();   // S10
  });
});

describe("refusals", () => {
  it("a PDF shows the Word-file message and sends no request; the copy we sent is Word only", () => {
    expect(fileRefusal(new File(["%PDF"], "returned.PDF"))).toBe(C.pdf);
    expect(copyRefusal(new File(["%PDF"], "sent.pdf"))).toBe(C.copyWord);
    expect(fileRefusal(new File(["x"], "notes.txt"))).toMatch(/Choose a Word file/);
    expect(fileRefusal(RETURNED)).toBeNull();
    expect(uploads).toEqual([]);
  });

  it("a clean Word file's NO_TRACKED_CHANGES switches to the copy we sent; a gone deal is the plain 404", () => {
    expect(refusalOf(new ApiError(422, "NO_TRACKED_CHANGES", "no marks", "r"), false)).toBe("no_tracked");
    expect(refusalOf(new ApiError(422, "WORD_FILE_NEEDED", "word", "r"), false)).toBe("word");
    expect(refusalOf(new ApiError(404, "NOT_FOUND", "x", "r"), true)).toBe("gone");
    expect(refusalOf(new ApiError(409, "CONFLICT", "archived", "r"), true)).toBe("closed");
    expect(refusalOf(new Error("network"), true)).toBe("other");
    expect(C.gone).not.toMatch(/not open to you|access/);                      // M8, 52.4
  });
});

describe("the uploads, in order", () => {
  const made = (): Made => ({ contractId: null, copyIn: false });
  const send = (over: Partial<Parameters<typeof sendReturned>[0]>) => sendReturned({
    deal: NEW_DEAL, clientId: "client-1", clientName: "Synthetic Client", file: RETURNED, copy: COPY, haveCopy: true, review: true,
    made: made(), onStep: () => undefined, ...over });

  it("(b) the copy we sent as our draft, then the returned file as the client's; no X-Compare-With", async () => {
    const out = await send({});
    expect(api.createContract).toHaveBeenCalledWith(expect.stringMatching(/^Contract with Synthetic Client, \d{1,2} [A-Z][a-z]{2} \d{4}$/), undefined, "client-1");
    expect(uploads.map(([id, f, role, compare]) => [id, (f as File).name, role, compare]))
      .toEqual([["c-new", "msa-sent.docx", "COMPANY_DRAFT", undefined], ["c-new", "msa-returned.docx", "CLIENT_MODIFIED", undefined]]);
    expect(contractHref(out.contractId, "changes")).toBe("/contracts/c-new/changes");     // the landing
  });

  it("(c) only the tracked-changes-only start sends X-Compare-With", async () => {
    await send({ haveCopy: false, copy: null });
    expect(uploads.map(([, f, role, compare]) => [(f as File).name, role, compare]))
      .toEqual([["msa-returned.docx", "CLIENT_MODIFIED", "TRACKED_ORIGINAL"]]);
  });

  it("(a) an existing deal takes the file as its next version, compared with ours there", async () => {
    await send({ deal: "c-old", copy: null });
    expect(api.createContract).not.toHaveBeenCalled();
    expect(uploads).toEqual([["c-old", RETURNED, "CLIENT_MODIFIED"]]);
  });

  it("the header travels on the request itself", async () => {
    vi.restoreAllMocks();
    const fetched = vi.fn(async () => new Response(JSON.stringify({ data: { document_version: { id: "v" } } }),
                                                   { status: 201, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetched);
    await api.uploadDocument("c1", RETURNED, "CLIENT_MODIFIED", "TRACKED_ORIGINAL");
    await api.uploadDocument("c1", RETURNED, "CLIENT_MODIFIED");
    const sent = fetched.mock.calls.map((c) => (c as unknown[])[1] as RequestInit);
    expect((sent[0]!.headers as Record<string, string>)["X-Compare-With"]).toBe("TRACKED_ORIGINAL");
    expect((sent[1]!.headers as Record<string, string>)["X-Compare-With"]).toBeUndefined();
    vi.unstubAllGlobals();
  });

  it("a failed returned upload resumes after the copy we sent: no second deal (M7)", async () => {
    const kept = made();
    vi.mocked(api.uploadDocument).mockImplementation(async (...args: unknown[]) => {
      uploads.push(args);
      if (args[2] === "CLIENT_MODIFIED" && uploads.length === 2) throw new ApiError(500, "INTERNAL", "x", "r");
      return { document_version: { id: "v" }, duplicate_of: null } as never;
    });
    await expect(send({ made: kept })).rejects.toThrow();
    await send({ made: kept });
    expect(api.createContract).toHaveBeenCalledTimes(1);
    expect(uploads.map((u) => u[2])).toEqual(["COMPANY_DRAFT", "CLIENT_MODIFIED", "CLIENT_MODIFIED"]);
  });

  it("the same file already on the deal stops before Changes (M7)", async () => {
    vi.mocked(api.uploadDocument).mockResolvedValue({ document_version: { id: "v" }, duplicate_of: "v1" } as never);
    expect(await send({ deal: "c-old", copy: null })).toEqual({ contractId: "c-old", duplicate: true });
  });

  it("a double click sends one request", async () => {
    let calls = 0;
    const once = singleFlight(async () => { calls += 1; await new Promise((r) => setTimeout(r, 5)); });
    await Promise.all([once(), once()]);
    expect(calls).toBe(1);
    await once();
    expect(calls).toBe(2);
  });
});

describe("the deal list", () => {
  const deal = (id: string, stage?: string) =>
    ({ id, name: id, ...(stage ? { negotiation_stage: { stage, since: "", days: 0 } } : {}) }) as Contract;
  it("omits FINAL and SIGNED; only a deal whose latest version is ours takes the file", () => {
    const rows = [deal("a", "DRAFTING"), deal("b", "FINAL"), deal("c", "SIGNED"), deal("d", "WITH_CLIENT"),
                  deal("e", "CLIENT_RETURNED"), deal("f", "READY_TO_SEND")];
    expect(dealsShown(rows).map((c) => c.id)).toEqual(["a", "d", "e", "f"]);
    expect(dealsShown(rows).filter(openForReturn).map((c) => c.id)).toEqual(["a", "d", "f"]);
    expect(C.dealLine("MSA", "With client", 3, "COMPANY_DRAFT", "23 Nov 2026"))
      .toBe("MSA. With client. Version 3 is ours. Last changed 23 Nov 2026.");      // N3, UI 4
  });
});

describe("the Changes tab, tracked changes only", () => {
  const list = { contract_id: "c", from: null, to: { document_version_id: "v1", version_number: 1 }, tracked_base: true,
                 summary: { total: 2, untracked: 0 }, changes: [], can_answer: true, can_decide: false } as unknown as ChangeList;
  it("shows the tracked-only banner and never the Convert bar or an untracked note", () => {
    const html = renderToStaticMarkup(<ChangesBanners data={list} allUntracked={false} />);
    expect(html).toContain("Compared with the client’s tracked changes only.");
    expect(html).not.toMatch(/made without tracking\)|Made from our blank template/);
    expect(convertOffered(list)).toBe(false);
    expect(convertOffered({ ...list, tracked_base: undefined } as unknown as ChangeList)).toBe(true);   // the client's own paper
  });

  it("names our side and offers no Keep ours until Legal answers (M4, M5)", () => {
    expect(oursLabel(list)).toBe("Before the client’s tracked changes");
    const change = { kind: "MODIFIED", route: "owner", review: { after: [] } } as unknown as ClientChange;
    expect(actionsFor(change, list)).not.toContain("keep_ours");
    expect(actionsFor(change, { ...list, tracked_base: undefined } as unknown as ChangeList)).toContain("keep_ours");
  });
});

describe("round 2: the refusals keep what the person chose (D2)", () => {
  const noop = () => undefined;
  it("two picks of one file are refused on the returned file, linked to it", async () => {
    expect(await sameFile(new File(["same bytes"], "sent.docx"), new File(["same bytes"], "back.docx"))).toBe(true);
    expect(await sameFile(new File(["ours"], "sent.docx"), new File(["theirs"], "back.docx"))).toBe(false);
    const html = renderToStaticMarkup(<ReturnedFile file={RETURNED} error={C.same} busy={false} existing={false}
                                                    onFile={noop} onAsTheirs={noop} />);
    expect(html).toContain(`id="rm-file-err" class="nc-error" role="alert" tabindex="-1">${C.same}`);
    expect(html).toMatch(/aria-invalid="true" aria-describedby="[^"]* rm-file-err"/);
    expect(html).toContain(RETURNED.name);                                  // the file stays chosen
  });

  it("NO_TRACKED_CHANGES keeps the client and the file and asks for the copy we sent", () => {
    const next = afterRefusal(refusalOf(new ApiError(422, "NO_TRACKED_CHANGES", "x", "r"), false));
    expect(next).toEqual({ focus: "rm-notracked", haveCopy: true, noTracked: true, forgetDeal: true });
    expect(next).not.toHaveProperty("dropFile");                            // the file is kept
    const html = renderToStaticMarkup(<BaseChoice haveCopy noTracked busy={false} copy={null} copyError={null}
                                                  copyTracked={false} onCopy={noop} onHave={noop} />);
    expect(html).toContain(`id="rm-notracked" class="ic-note ic-note--alert" role="alert" tabindex="-1"`);
    expect(html).toContain(C.noTracked);
    expect(html).toMatch(/name="rm-base" checked=""/);                     // "Yes, I have the copy we sent"
    expect(html).toMatch(/type="radio" disabled="" aria-describedby="rm-notracked" name="rm-base"/);   // UI 2
  });
});
