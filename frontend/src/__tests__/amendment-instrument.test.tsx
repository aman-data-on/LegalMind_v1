/**
 * `AM-310` (Q-9 decided as research 13 (c)): an amendment is the changes-only instrument;
 * restating the whole contract is Legal's secondary choice, shown with its warning and
 * never selected for them; the terms in force say they are not binding, on screen and
 * on paper. Static render, house idiom.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: () => {} }) }));
vi.mock("@/lib/session", () => ({ useSession: () => ({ can: () => true, identity: null }) }));

import { GovernedByLink } from "@/components/workspace/Amendments";
import { PackageBar, RESTATE_WARNING } from "@/components/workspace/Package";
import { NOT_BINDING, TermsView } from "@/components/workspace/TermsInForce";
import { nextStep } from "@/lib/nextStep";
import { AMENDMENT_PLACE, finalLine, type PackagePlan } from "@/lib/package";
import type { EffectiveText } from "@/lib/types";

const plan = (extra: Partial<PackagePlan> = {}): PackagePlan => ({
  available: true, blockers: [], precedence: null, entries_sha256: "a".repeat(64), form: "changes_only",
  entries: [{ n: 1, op: "replace", target: { key: "K~8.5", number: "8.5", heading: null }, text: "Thirty days." }],
  ...extra });
const bar = (p: PackagePlan, canRestate: boolean) => renderToStaticMarkup(
  <PackageBar contractId="c" plan={p} canPrepare canRestate={canRestate} nextVersion={3}
              onReload={() => {}} onPrepared={() => {}} onPick={() => {}} />);

describe("the amendment bar", () => {
  it("is the changes-only amendment, and restating is never offered to a non-holder", () => {
    const html = bar(plan(), false);
    expect(html).toContain("A short amendment listing only the 1 agreed change");
    expect(html).not.toContain("Restate the whole contract");
    expect(html).not.toContain("Annexure A");
  });
  it("offers restating to Legal as a secondary action, with the warning, and the triggers as Legal's call", () => {
    const html = bar(plan({ restatement: ["This contract already has 3 signed amendments."] }), true);
    expect(html).toContain("Restate the whole contract instead");
    expect(RESTATE_WARNING).toContain("can be read as a new contract and may need fresh stamp duty");
    expect(html).toContain("can be read as a new contract and may need fresh stamp duty. Use only on Legal’s advice.");
    expect(html).toContain("That is Legal’s call: This contract already has 3 signed amendments.");
    expect(html).not.toMatch(/ws-btn--primary[^>]*>Restate/);               // never the primary
    expect(html).not.toMatch(/confiden|likely|probab/i);
  });
  it("names the step and the change rows for an amendment", () => {
    expect(nextStep({ stage: "CLIENT_RETURNED", counts: { changes_total: 1, changes_left: 0, points_open: 0 }, viewer: "owner",
                      canAnswer: true, packageReady: true, amendment: true })?.label).toBe("Prepare amendment");
    expect(finalLine({ answer: null, target: { key: "k", number: "8.5", heading: null }, in_package: "replace" },
                     AMENDMENT_PLACE)).toBe("Goes into the amendment, replacing clause 8.5");
  });
});

describe("the conformed copy", () => {
  const text: EffectiveText = { contract_id: "c", amendments: [],
    original: { document_version_id: "v", version_number: 4, read: "APPLIED", clauses: [] },
    current: { read: "APPLIED", removed: [], clauses: [{ number: "1", heading: null, text: "A clause." }] } };
  it("says it is not binding, and can be printed with that line", () => {
    const html = renderToStaticMarkup(<TermsView contractId="c" contract={null} text={text} />);
    expect(NOT_BINDING).toBe("For reference only, not binding. The agreed contract and its agreed amendments govern.");
    expect(html).toContain("For reference only, not binding.");
    expect(html).toContain("Print or save as PDF");
  });
  it("is linked from the amendment's own page", () => {
    const html = renderToStaticMarkup(<GovernedByLink contract={{ governed_by: { id: "p", name: "Signed MSA", contract_type: "MSA" } }} />);
    expect(html).toContain('href="/contracts/p/terms"');
  });
});
