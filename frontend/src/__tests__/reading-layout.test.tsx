/**
 * CLM UI pass 2 (owner, 2026-11-02): the reading view set as a contract, the reply's
 * notice, the version roles, the Changes list labels. Presentation only — the text a
 * row renders is always exactly its evidence string.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ReplyNotice, rowLabel } from "@/components/workspace/ChangesPane";
import { versionRoleLabel } from "@/components/workspace/model";
import { readingLayout, readingPieces } from "@/components/workspace/reading";
import { contractDisplayName } from "@/lib/labels";
import type { ClientChange } from "@/lib/changes";
import type { DocumentVersion } from "@/lib/types";

const row = (content: string, extra: { section_number?: string; is_heading?: boolean } = {}) =>
  ({ content, section_number: extra.section_number ?? null, is_heading: extra.is_heading ?? false });

describe("readingLayout", () => {
  const lines = readingLayout([
    row("This Agreement is entered into by LeapSwitch of the ONE PART;"),
    row("AND"),
    row("WHEREAS,"),
    row("A. The Customer wishes to avail of the Services;"),
    row("DEFINITIONS AND INTERPRETATION", { section_number: "1", is_heading: true }),
    row("1.1 Defined Terms: Capitalised terms have these meanings:"),
    row("(h) “Service” means the hosting service."),
    row("(i) “Term” means one year."),
    row("4.3 Change Request Procedure: the following process applies:"),
    row("i. A request is made in writing."),
    row("4.3.1 Change Initiation: a change is initiated by a request."),
    row("LeapSwitch shall inform the Customer as soon as possible."),
  ]);

  it("centres connectors and labels the recitals", () => {
    expect(lines[1]!.shape).toBe("connector");
    expect(lines[2]!.shape).toBe("label");
    expect(lines[3]).toMatchObject({ indent: 0, lead: 3 });          // "A. " hung
    expect(lines[0]).toMatchObject({ indent: 0, lead: 0, hang: 0 }); // preamble
  });

  it("hangs every number in a gutter, one consistent step per level", () => {
    expect(lines[4]).toMatchObject({ num: "1", indent: 0, lead: 0 }); // the parser's number
    expect(lines[5]).toMatchObject({ indent: 720 / 240, hang: 720 / 240, lead: 4 }); // 0.5in at 12pt
    const body = lines[5]!.indent + lines[5]!.hang;
    expect(lines[6]).toMatchObject({ indent: body, lead: 4 });       // (h) under 1.1's text
    expect(lines[7]!.indent).toBe(body);                              // (i) after (h): a letter
    expect(lines[9]!.indent).toBe(body);                              // i. under 4.3's text
    expect(lines[10]).toMatchObject({ indent: 1440 / 240, hang: 720 / 240 }); // 4.3.1 one step in
    // an unnumbered paragraph continues the clause it follows, at its text
    expect(lines[11]!.indent).toBe(lines[10]!.indent + lines[10]!.hang);
  });

  it("uses the generated contract's ladder (house.json clause_ladder_twips) to level five", () => {
    const deep = readingLayout(["2.1 A.", "2.1.1 B.", "2.1.1.1 C.", "2.1.1.1.1 D."].map((t) => row(t)));
    const twips = deep.map((l) => [l.indent * 240, (l.indent + l.hang) * 240].map(Math.round));
    expect(twips).toEqual([[720, 1440], [1440, 2160], [2160, 2880], [2880, 3600]]);
  });

  it("hangs a list number the text does not carry (a generated contract's 2.1.1) on the ladder", () => {
    const [l] = readingLayout([row("Clause A.1.1 text.", { section_number: "2.1.1" })]);
    expect(l).toMatchObject({ num: "2.1.1", lead: 0, indent: 1440 / 240, hang: 720 / 240 });
    // a number the text already states is not drawn twice
    expect(readingLayout([row("2.1 the fees.", { section_number: "2.1" })])[0]!.num).toBeNull();
  });

  it("never reads a sentence that opens with a figure as a clause number", () => {
    expect(readingLayout([row("12 months after the date the fees fall due.")])[0]!.lead).toBe(0);
  });
});

describe("readingPieces", () => {
  const content = "(b) “Agreement” shall mean all this Agreement, dated January, 2025.";
  const join = (p: { text: string }[]) => p.map((x) => x.text).join("");

  it("always rejoins to the evidence string exactly", () => {
    const { pieces } = readingPieces(content, {
      lead: 4, marks: true,
      changes: [{ deleted: "03 September", inserted: "January" }, { deleted: ",", inserted: "" }],
      annotations: [{ id: "a", rowId: "r", start: 20, end: 30, note: "", created: "" }],
    });
    expect(join(pieces)).toBe(content);
    expect(pieces[0]).toMatchObject({ text: "(b) ", lead: true });
    expect(pieces.find((p) => p.term)?.text).toBe("“Agreement”");
    expect(pieces.find((p) => p.ins)).toMatchObject({ text: "January", ins: { del: "03 September" } });
    expect(pieces.some((p) => p.annotation)).toBe(true);
  });

  it("leaves what it cannot place for the note, and marks nothing with changes hidden", () => {
    const placed = readingPieces(content, { lead: 4, marks: true,
      changes: [{ deleted: "x", inserted: "a" }, { deleted: ";", inserted: "" }] });
    expect(placed.unplaced).toEqual([{ deleted: "x", inserted: "a" }, { deleted: ";", inserted: "" }]);
    const off = readingPieces(content, { lead: 4, marks: false,
      changes: [{ deleted: "03 September", inserted: "January" }] });
    expect(off.pieces.some((p) => p.ins)).toBe(false);
    expect(off.unplaced).toEqual([]);
  });
});

const v = (id: string, n: number, extra: Partial<DocumentVersion> = {}) =>
  ({ id, version_number: n, original_filename: "x.docx", ...extra }) as DocumentVersion;

describe("the version switcher says what each version is", () => {
  const theirs = v("v2", 2, { version_role: "CLIENT_MODIFIED" });
  const reply = v("v3", 3, { version_role: "COMPANY_DRAFT", reply: { to_version_id: "v2" } });
  const all = [reply, theirs, v("v1", 1, { version_role: "COMPANY_DRAFT" })];
  it("names ours, the client's, our reply and signed — and nothing nobody declared", () => {
    expect(all.map((x) => versionRoleLabel(x, all))).toEqual(["Our reply to v2", "Client's", "Ours"]);
    expect(versionRoleLabel(v("v4", 4, { version_role: "FINAL_SIGNED" }), all)).toBe("Signed");
    expect(versionRoleLabel(v("v5", 5), all)).toBeNull();
  });

  it("the reply's notice states the round, its counts and the files; sent, when", () => {
    const withCounts = { ...reply, reply: { to_version_id: "v2", tracked: 81, by_hand: ["Support"] } };
    const html = renderToStaticMarkup(<ReplyNotice version={withCounts} versions={all} canSend />);
    expect(html).toContain("Version 3 is our reply to the client’s version 2");
    expect(html).toContain("81 of our changes are in it as tracked changes; 1 to restore by hand in Word (Support)");
    expect(html).toMatch(/Download <\/span>Word/);
    expect(html).toMatch(/Download <\/span>PDF/);   // fetched on click: AM-293 may refuse it
    const sent = renderToStaticMarkup(
      <ReplyNotice version={{ ...withCounts, sent_at: "2026-11-02T10:00:00Z" }} versions={all} canSend={false} />);
    expect(sent).toContain("Sent to the client on 2 November 2026");
    expect(renderToStaticMarkup(<ReplyNotice version={theirs} versions={all} canSend />)).toBe("");
  });
});

it("a Changes row that would only repeat its group's heading says its first words", () => {
  const change = { clause: { number: "3", heading: null }, page: 3,
                   after: { evidence_ids: [], text: "SERVICES:" }, before: null } as unknown as ClientChange;
  expect(rowLabel(change, "3")).toBe("3 SERVICES:");
  expect(rowLabel(change, "4")).toBe("3 SERVICES:");   // never a bare number (page 3)
});

describe("a generated contract (house styles)", () => {
  const house = (content: string, house_style: string, section_number: string | null = null) =>
    ({ content, section_number, is_heading: false, house_style });
  const lines = readingLayout([
    house("MASTER SERVICES AGREEMENT", "LM Title"),
    house("Party One Limited, a company …", "LM Recital"),
    house("AND", "LM Connector"),
    house("Party Two Limited, a company …", "LM Recital"),
    house("WHEREAS", "LM Plain Heading"),
    house("Recital one.", "LM Recital"),
    house("DEFINITIONS", "LM Heading 1", "1"),
    house("“Affiliate” shall mean:", "LM Heading 2", "1.1"),
    house("SCOPE", "LM Heading 1", "4"),
    house("Term: the term.", "LM Heading 2", "4.1"),
  ]);
  it("letters the parties and the recitals, hangs them 1cm, keeps AND at their text", () => {
    expect(lines.map((l) => l.num)).toEqual(
      [null, "A.", null, "B.", null, "A.", "1.", "1.1.", "4.", "4.1."]);
    expect(lines[1]).toMatchObject({ indent: 0, hang: 567 / 240 });
    expect(lines[2]).toMatchObject({ indent: 567 / 240, hang: 0 });
  });
  it("sets every clause on the one house ladder (Round 6)", () => {
    const twips = (i: number) => [lines[i]!.indent * 240, (lines[i]!.indent + lines[i]!.hang) * 240].map(Math.round);
    expect(twips(6)).toEqual([0, 720]);      // 1.: number at the margin, text 0.5in
    expect(twips(7)).toEqual([720, 1440]);   // 1.1 as 4.1: number 0.5in, text 1in
    expect(twips(9)).toEqual([720, 1440]);
  });
  it("splits at the file's own bold and underline, rejoining to the evidence exactly", () => {
    const content = "Term: This Agreement starts.";
    const { pieces } = readingPieces(content, { lead: 0, marks: false, emphasis: [[0, 5, "u"]] });
    expect(pieces.map((p) => p.text).join("")).toBe(content);
    expect(pieces[0]).toMatchObject({ text: "Term:", underline: true });
  });
});

describe("contractDisplayName", () => {
  it("title-cases an all-capitals part and leaves the rest as written", () => {
    expect(contractDisplayName("MASTER SERVICES AGREEMENT — Demo Client Private Limited"))
      .toBe("Master Services Agreement — Demo Client Private Limited");
    expect(contractDisplayName("NDA — ACME")).toBe("NDA — ACME");
    expect(contractDisplayName("TERMS OF SERVICE")).toBe("Terms of Service");
  });
});
