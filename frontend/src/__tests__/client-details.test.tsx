/**
 * Batch 7 (AB-220): the Client details card and the panel's "Still needed", in every state
 * the server can send — nothing here computes a state (rule 18). Synthetic data only.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ClientDetailsCard } from "@/components/newcontract/ClientDetailsCard";
import { IntakeSteps } from "@/components/newcontract/IntakeSteps";
import { StillNeeded } from "@/components/newcontract/StillNeeded";
import type { ChecklistItem, ClientChecklist } from "@/lib/clientDetails";
import { INTAKE_COPY } from "@/lib/labels";
import type { Counterparty } from "@/lib/types";

const KEYS = ["agreement_date", "registered_email", "registered_office", "cin", "business", "signatory_name",
  "signatory_designation", "signatory_email", "gstin", "gst_certificate"];
const FIELDS: Record<string, string> = { registered_email: "registered_email", registered_office: "registered_office",
  cin: "cin_or_llpin", business: "line_of_business", signatory_name: "signatory_name",
  signatory_designation: "signatory_designation", signatory_email: "signatory_email", gstin: "gstin",
  gst_certificate: "gst_certificate" };

function items(status: (key: string) => ChecklistItem["status"] = () => "missing"): ChecklistItem[] {
  return KEYS.map((key, i): ChecklistItem => ({ n: i + 1, key, status: status(key), source: i ? "profile" : "deal",
    ...(i ? { profile_field: FIELDS[key]! } : { question: "effective_date" }) }));
}
function list(over: Partial<ClientChecklist> = {}): ClientChecklist {
  return { applies: true, ready: false, items: items(), warnings: [], india: true, questions: [], reads: [],
    verify_needed: true, verified: null, counts: { done: 0, needed: 9 }, client_ready: false, can_edit: true, ...over };
}
const CLIENT: Counterparty = { id: "c1", name: "Zeta", status: "ACTIVE", created_at: null, updated_at: null };
const card = (c: ClientChecklist, client: Counterparty = CLIENT, refused = false) =>
  renderToStaticMarkup(<ClientDetailsCard client={client} checklist={c} refused={refused} onClient={() => {}} />);
const text = (html: string) => html.replace(/<[^>]+>/g, " ").replace(/&#x27;/g, "'").replace(/&quot;/g, '"')
  .replace(/&amp;/g, "&");

describe("the Client details card", () => {
  it("starts with the certificate and shows nothing filled yet in neutral words", () => {
    const html = card(list());
    expect(text(html)).toContain(INTAKE_COPY.upload);
    expect(html.indexOf(INTAKE_COPY.groups.certificate)).toBeLessThan(html.indexOf(INTAKE_COPY.groups.signs));
    expect(html).not.toContain(INTAKE_COPY.status.missing);       // an empty field is bare
    expect(html).not.toContain(INTAKE_COPY.status.refused);
    expect(html).not.toContain("Missing");               // never the point status's word
  });

  it("says what Create still needs in orange only once Create was refused", () => {
    expect(card(list(), CLIENT, true)).toContain('data-tone="refused"');
  });

  it("marks a value read from the certificate until a person confirms it", () => {
    const reads = [{ field: "gstin", value: "27AAACZ9999Q1Z5", state: "fill" as const },
      { field: "pan", value: "AAACZ9999Q", state: "fill" as const },
      { field: "registered_office", value: "Unit 9, Pune, Maharashtra", state: "differs" as const }];
    const client = { ...CLIENT, registered_office: "Old address", gst_certificate: {
      filename: "gst.pdf", mime_type: "application/pdf", size_bytes: 10, uploaded_at: "2026-11-23T00:00:00Z",
      read: { state: "Maharashtra" } } };
    const html = card(list({ reads }), client);
    expect(html).toContain(INTAKE_COPY.marker);
    expect(html).toContain('value="27AAACZ9999Q1Z5"');
    expect(html).toContain(INTAKE_COPY.confirmAll(1));                    // the PAN rides along
    expect(text(html)).toContain(INTAKE_COPY.differs("Unit 9, Pune, Maharashtra"));
    expect(text(html)).toContain(INTAKE_COPY.derived("AAACZ9999Q", "Maharashtra"));
  });

  it("names a value to fix and a check that only warns", () => {
    const html = card(list({ items: items((k) => (k === "gstin" ? "fix" : "done")).map((i) =>
      i.key === "gstin" ? { ...i, problem: "pan_mismatch" } : i),
    warnings: [{ code: "act_wording", item: 4, year: 2010 }] }));
    expect(text(html)).toContain(INTAKE_COPY.problems.pan_mismatch);
    expect(text(html)).toContain(INTAKE_COPY.warnings.act_wording(2010));
  });

  it("says not needed for a company outside India and asks no tick", () => {
    const abroad = list({ india: false, verify_needed: false,
      items: items((k) => (["cin", "gstin", "gst_certificate"].includes(k) ? "not_needed" : "missing")) });
    const html = card(abroad);
    expect(html).toContain(INTAKE_COPY.abroad);
    expect(html).not.toContain(INTAKE_COPY.markChecked);
  });

  it("collapses to one line when everything is on file and checked", () => {
    const html = card(list({ client_ready: true, verified: { at: "2026-11-20T00:00:00Z", by: "Priya" } }));
    expect(html).toContain(INTAKE_COPY.onFile);
    expect(html).toContain("Checked by Priya");
    expect(html).not.toContain("<input");
  });

  it("is read only for whoever may not edit the client", () => {
    const html = card(list({ can_edit: false }));
    expect(html).toContain(INTAKE_COPY.readOnly);
    expect(html).not.toContain("<input");
    expect(html).not.toContain(INTAKE_COPY.markChecked);
  });

  it("offers the check only once what it attests is there, with the records' links", () => {
    expect(card(list())).toMatch(/<button[^>]*disabled=""[^>]*>Mark as checked/);
    const ready = card(list({ items: items(() => "done"), tick_ready: true }));
    expect(ready).not.toMatch(/disabled=""[^>]*>Mark as checked/);
    expect(ready).toContain("(opens in a new tab)");
  });

  it("offers an older draft's typed answer, and says the certificate's GST number could not be read", () => {
    const client = { ...CLIENT, gst_certificate: { filename: "gst.pdf", mime_type: "application/pdf", size_bytes: 10,
      uploaded_at: "2026-11-23T00:00:00Z", read: { gstin_unreadable: "true" } } };
    const html = text(card(list({ draft_values: { signatory_email: "old@zeta.example.test" } }), client));
    expect(html).toContain(INTAKE_COPY.fromDraft);
    expect(html).toContain(INTAKE_COPY.gstinUnreadable);
  });

  it("asks the Country from a list, keeps an older typed one readable, and says outside India once", () => {
    expect(text(card(list()))).toContain(INTAKE_COPY.countryIndia);
    const legacy = card(list(), { ...CLIENT, country: "Bharat (old)" });
    expect(legacy).toMatch(/<select id="ic-f-country"/);
    expect(legacy).toMatch(/<option value="Bharat \(old\)" selected="">/);
    expect(legacy).toContain('<option value="Germany">');
    const abroad = list({ india: false, verify_needed: false, country_abroad: "Germany",
      items: items((k) => (["cin", "gstin", "gst_certificate"].includes(k) ? "not_needed" : "missing")) });
    const cert = { filename: "gst.pdf", mime_type: "application/pdf", size_bytes: 10, uploaded_at: "2026-11-23T00:00:00Z" };
    for (const client of [{ ...CLIENT, country: "Germany" }, { ...CLIENT, country: "Germany", gst_certificate: cert }]) {
      const html = text(card(abroad, client));
      expect(html.match(/outside India/g)).toHaveLength(1);
      expect(html).not.toContain(INTAKE_COPY.countryIndia);
    }
  });

  it("ticks each finished group and keeps saying a read value came from the certificate", () => {
    const done = list({ items: items(() => "done"), verified: { at: "2026-11-20T00:00:00Z", by: "Priya" },
      reads: [{ field: "gstin", value: "27AAACZ9999Q1ZU", state: "same" }] });
    const html = card(done, { ...CLIENT, legal_name: "ZETA SYNTHETIC PRIVATE LIMITED", gstin: "27AAACZ9999Q1ZU" });
    expect(html.match(/class="ic-group__done"/g)).toHaveLength(4);
    expect(html).toContain(INTAKE_COPY.fromCertificate);
    expect(card(done).match(/class="ic-group__done"/g)).toHaveLength(3);   // no legal name: not complete
  });

  it("speaks the reader's words only: no codes, ids or engine terms", () => {
    const html = text(card(list({ warnings: [{ code: "state_unreadable", item: 9 }] })));
    expect(html).not.toMatch(/[A-Z]{2,}[-_][A-Z0-9_]|AM-[0-9]|§|Constitution|requirement|evaluat|deviation|classification|\*\*|##/);
  });
});

describe("the panel's Still needed", () => {
  it("lists the nine client details and the check, and the agreement date under This deal", () => {
    const html = renderToStaticMarkup(
      <StillNeeded checklist={list()} refused={false} dealDone={0} dealAsked={1} onClientItem={() => {}} onQuestion={() => {}}
                   dealLeft={[{ key: "effective_date", label: INTAKE_COPY.items.agreement_date! }]} />);
    const rows = html.match(/class="ic-needed__row"/g) ?? [];
    expect(rows).toHaveLength(11);                            // 9 + the check + the date
    expect(html.match(/class="ic-state"/g)).toHaveLength(11);  // one state each
    expect(html).toContain(INTAKE_COPY.notChecked);
    expect(html).toContain(INTAKE_COPY.added(0, 9));
  });
});

describe("the panel, client details finished", () => {
  it("is one line that opens on demand", () => {
    const html = renderToStaticMarkup(
      <StillNeeded checklist={list({ items: items(() => "done"), client_ready: true, counts: { done: 9, needed: 9 },
        verified: { at: "2026-11-20T00:00:00Z", by: "Priya" } })}
                   refused={false} dealDone={0} dealAsked={0} onClientItem={() => {}} onQuestion={() => {}} dealLeft={[]} />);
    expect(html).toMatch(/<details class="ic-needed__done"[^>]*><summary>/);
    expect(html).not.toMatch(/<details[^>]* open/);
  });
});

describe("the panel, a value read and not confirmed", () => {
  it("is neither filled nor missing: it says it was read", () => {
    const html = renderToStaticMarkup(
      <StillNeeded checklist={list({ reads: [{ field: "gstin", value: "27AAACZ9999Q1ZU", state: "fill" }] })}
                   refused={false} dealDone={0} dealAsked={0} onClientItem={() => {}} onQuestion={() => {}} dealLeft={[]} />);
    expect(html).toContain(INTAKE_COPY.readState);
  });
});

describe("the steps", () => {
  it("are four, say where each stands in words, and mark the current one", () => {
    const html = renderToStaticMarkup(<IntakeSteps step={2} done={{ 1: true }} notes={{ 2: INTAKE_COPY.added(7, 9) }} />);
    expect(html.match(/<li/g)).toHaveLength(4);
    expect(html).toContain('aria-current="step"');
    expect(html).toContain("7 of 9 added");
    expect(html).not.toMatch(/%/);
  });
});
