/**
 * Terms in force (`AM-309`, R-9) — static render. Pins the quiet note on a changed clause
 * (which amendment, when, linked), "an amendment" when the reader cannot open it (SEC-07),
 * and the fail-closed state: the server's reason, no text shown as in force (rule 15).
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {} }) }));

import { AmendmentsPanel } from "@/components/workspace/Amendments";
import { TermsView } from "@/components/workspace/TermsInForce";
import type { EffectiveText } from "@/lib/types";

const original = { document_version_id: "v4", version_number: 4, read: "APPLIED", clauses: [] };
const amendments = [{ contract_id: "a1", name: "Amendment one", signed_at: "2026-11-04T10:00:00+05:30",
                      document_version_id: "a4", applied: true }];
const text = (current: EffectiveText["current"]): EffectiveText =>
  ({ contract_id: "c", original, amendments, current });

describe("Terms in force", () => {
  it("marks a changed clause with the amendment that changed it, linked, and the wording before", () => {
    const html = renderToStaticMarkup(<TermsView contractId="c" contract={null} text={text({ read: "APPLIED", removed: [],
      clauses: [{ number: "8.4", heading: null, text: "Unchanged clause." },
                { number: "8.5", heading: null, text: "Pay within thirty (30) days.",
                  original: "Pay within fifteen (15) days.", by: "a1" }] })} />);
    expect(html).toContain("Changed by <a href=\"/contracts/a1\">Amendment No. 1</a>, signed 4 Nov 2026");
    expect(html).toContain("Wording before");
    expect(html).toContain("fifteen (15) days");
    expect(html.match(/Changed by/g)).toHaveLength(1);           // only the changed clause
    expect(html).toContain("1 clause is changed");
    expect(html).not.toMatch(/confiden|likely|probab/i);
  });

  it("never names an amendment the reader cannot open, and says added and removed", () => {
    const html = renderToStaticMarkup(<TermsView contractId="c" contract={null} text={text({ read: "APPLIED",
      clauses: [{ number: "4.1", heading: null, text: "Hidden change.", original: "Before." },
                { number: "4.2A", heading: null, text: "New clause.", original: null, by: "a1" }],
      removed: [{ number: "5", heading: null, text: "Gone.", by: "a1" }] })} />);
    expect(html).toContain("Changed by an amendment");
    expect(html).toContain("Added by <a href=\"/contracts/a1\">Amendment No. 1</a>");
    expect(html).toContain("Clause 5");
    expect(html).toContain("Removed by <a href=\"/contracts/a1\">Amendment No. 1</a>");
  });

  it("fails closed: the server's reason, and no clause shown as in force", () => {
    const html = renderToStaticMarkup(<TermsView contractId="c" contract={null} text={text({ read: "NOT_APPLIED",
      reason: "An amendment: it was not made from the text in force before it." })} />);
    expect(html).toContain("The terms in force can’t be shown");
    expect(html).toContain("An amendment: it was not made from the text in force before it.");
    expect(html).not.toContain("ws-page");
    expect(html).toContain('href="/contracts/c"');
  });

  it("is reached from the Amendments panel once an amendment is signed", () => {
    const signed = [{ id: "a1", name: "A", status: "DRAFT", signed: true, archived: false }];
    expect(renderToStaticMarkup(<AmendmentsPanel contract={{ id: "c", amendments: signed }} canStart={false} />))
      .toContain('href="/contracts/c/terms"');
    expect(renderToStaticMarkup(<AmendmentsPanel contract={{ id: "c", amendments: [{ ...signed[0]!, signed: false }] }}
                                                 canStart={false} />)).not.toContain("/terms");
  });
});
