/**
 * Record signing (CLM flow 5, `AM-292`): the header's one step at Ready to sign, and the
 * form helpers. Every gate is the server's; these pin only what the screen shows.
 */
import { describe, expect, it } from "vitest";

import { cleaned, partyRows, signatoriesRecorded, stampRecorded, toFields, type ExecutionRecord } from "@/lib/execution";
import { nextStep } from "@/lib/nextStep";

describe("Record signing", () => {
  it("is never a step any more: Ready for the final contract prepares it (AM-318)", () => {
    expect(nextStep({ viewer: "owner", canAnswer: true, stage: "READY_TO_SIGN" })?.label).toBe("Prepare final contract");
    expect(nextStep({ viewer: "owner", canAnswer: false, stage: "READY_TO_SIGN" })).toBeNull();
    expect(nextStep({ viewer: "owner", canAnswer: true, stage: "SIGNED" })).toBeNull();
  });

  it("always shows both parties, in order, keeping what was recorded", () => {
    const rows = partyRows([{ party: "CLIENT", name: "B" }]);
    expect(rows.map((r) => r.party)).toEqual(["OURS", "CLIENT"]);
    expect(rows[1]!.name).toBe("B");
    expect(signatoriesRecorded(rows)).toBe(false);
    expect(signatoriesRecorded([
      { party: "OURS", name: "A", designation: "Director", authority_reference: "BR 1" },
      { party: "CLIENT", name: "B", designation: "CFO", authority_reference: "Letter 2" }])).toBe(true);
  });

  it("marks the stamp recorded only with every detail, or the acknowledgement", () => {
    expect(stampRecorded({ stamp_method: "E_STAMP", stamp_reference: "IN-1", stamp_state: "MH" })).toBe(false);
    expect(stampRecorded({ stamp_method: "E_STAMP", stamp_reference: "IN-1", stamp_state: "MH", duty_paid: "500" }))
      .toBe(true);
    expect(stampRecorded({ stamp_method: "NOT_STAMPED" })).toBe(false);
    expect(stampRecorded({ stamp_method: "NOT_STAMPED", not_stamped_acknowledged: true })).toBe(true);
  });

  it("sends blanks as nothing and the duty exactly as typed", () => {
    const out = cleaned({ duty_paid: " ₹500 ", stamp_state: "  ", witnesses: ["", " W "] });
    expect(out.duty_paid).toBe("₹500");
    expect(out.stamp_state).toBeNull();
    expect(out.witnesses).toEqual(["W"]);
  });

  it("starts from the server's pre-fill when nothing is recorded", () => {
    const f = toFields({ execution: null, comparison: null, blockers: [], signed: false,
                         prefill: { signatories: [{ party: "CLIENT", name: "From profile" }] } });
    expect(f.signatories?.[1]?.name).toBe("From profile");
  });
});

describe("a long clause that differs", () => {
  it("shows the words around the first difference, not the clause's opening", async () => {
    const { clip, firstDifference } = await import("@/components/workspace/SigningSheet");
    const head = "x".repeat(600);
    const d = { agreed_text: `${head} within 30 days`, signed_text: `${head} within 45 days` };
    const at = firstDifference(d);
    expect(at).toBe(608);
    expect(clip(d.signed_text, at)).toContain("45 days");
    expect(clip(d.signed_text, at).startsWith("…")).toBe(true);
    expect(clip("short")).toBe("short");
  });
});

describe("signed outside LegalMind (AM-298)", () => {
  const record: ExecutionRecord = { version: 1, signatories: [], stamp_method: null, stamp_reference: null, stamp_state: null,
    duty_paid: null, stamped_on: null, not_stamped_acknowledged: false, seal_used: null, witnesses: [],
    signed_document_version_id: "v", differences_accepted: false, differences_reason: null, signed_at: null,
    recorded_at: "2026-11-03" };
  it("shows a legacy signed version as signed, with no record asked for", async () => {
    const { signingView } = await import("@/lib/execution");
    expect(signingView({ execution: null, comparison: null, blockers: [], signed: true, legacy: true })).toBe("legacy");
  });
  it("keeps a filed record editable until confirmed, then final", async () => {
    const { signingView } = await import("@/lib/execution");
    const filed = { execution: { ...record, origin: "SIGNED_OUTSIDE" as const }, comparison: null, blockers: [], signed: true };
    expect(signingView({ ...filed, confirmed: false })).toBe("filed");
    expect(signingView({ ...filed, confirmed: true })).toBe("summary");
    expect(signingView({ ...filed, execution: { ...record }, signed: false })).toBe("form");
  });
});

describe("the signing record's authority line (polish batch)", () => {
  it("never says the kind or the date twice", async () => {
    const { authorityWords, signedWords } = await import("@/components/workspace/SigningSheet");
    expect(authorityWords({ authority_kind: "BOARD_RESOLUTION", authority_reference: "Board resolution of 1 Oct 2026",
                            authority_date: null })).toBe("Board resolution of 1 Oct 2026");
    expect(authorityWords({ authority_kind: "BOARD_RESOLUTION", authority_reference: "BR/2026/14",
                            authority_date: "2026-10-01" })).toBe("Board resolution BR/2026/14 of 1 Oct 2026");
    expect(authorityWords({ authority_kind: "AUTHORITY_LETTER", authority_reference: "Letter dated 1 Oct 2026",
                            authority_date: "2026-10-01" })).toBe("Authority letter Letter dated 1 Oct 2026");
    expect(authorityWords({ authority_kind: null, authority_reference: "", authority_date: null })).toBe("");
    expect(signedWords({ method: "E_SIGN", signed_on: "2026-11-02" })).toBe("E-signed on 2 Nov 2026");
    expect(signedWords({ method: null, signed_on: "2026-11-02" })).toBe("Signed on 2 Nov 2026");
    expect(signedWords({ method: null, signed_on: null })).toBe("");
  });
});
