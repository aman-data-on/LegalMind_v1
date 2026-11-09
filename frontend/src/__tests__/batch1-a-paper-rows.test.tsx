/**
 * UX Batch 1 slice A — a point on the client's paper says why it goes to Legal, names
 * no passage nothing confirmed, and the single-version tab opens exactly when the
 * server lists it. Static render, house idiom; the fields are the server's.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/session", () => ({
  useSession: () => ({ identity: { permissions: [] }, can: () => true }),
  useSeesLegalPosition: () => true,
}));
vi.mock("@/components/Dialog", () => ({ Dialog: ({ children }: { children: React.ReactNode }) => <div>{children}</div> }));

import { AnswerCard, ForUs, changesEnabled } from "@/components/workspace/ChangesPane";
import { matches, where, type ChangeList, type ClientChange } from "@/lib/changes";
import { offerFor, type PlaybookPoint } from "@/lib/playbook";
import type { DocumentVersion } from "@/lib/types";

const theirs = (over: Partial<ClientChange> = {}): ClientChange => ({
  row_key: "N|THEIRS|PT-1|e1", kind: "THEIRS", moved: false,
  clause: { number: null, heading: null, under: null }, clauses: [],
  candidates: [{ number: "7", heading: "Assignment" }, { number: "12", heading: "Taxes" }],
  page: null, before: null, after: null, tracked: false, untracked: false,
  review: { before: [], after: [{ finding_id: "f1", requirement_code: "PT-1",
    classification: "UNABLE_TO_EVALUATE", user_status: "NEEDS_DECISION", evaluation_ids: ["e1"] }] },
  review_delta: [], triage: null, route: "holder", route_reason: "MEASURED_BY_A_STANDARD",
  effect_for_us: "NEGATIVE", measured: "NOT_MEASURED", holder_accepted: false,
  answer: null, history: [], ...over,
});
const list: ChangeList = {
  contract_id: "c", from: null, to: { document_version_id: "v1", version_number: 1 },
  summary: { total: 1, untracked: 0 }, changes: [], can_answer: true, can_decide: false,
};
const POINT: PlaybookPoint = { requirement_code: "PT-1", kind: "RANGE", opening: null, line: "l", room: true };
const card = (c: ClientChange) => renderToStaticMarkup(
  <AnswerCard change={c} list={list} contractId="c" onAnswered={() => {}} onReload={() => {}} />);

describe("why a NEGATIVE row goes to Legal", () => {
  it("never calls an unmeasured row worse, nor beyond our offer", () => {
    const c = theirs();
    const html = card(c);
    expect(html).not.toContain("Worse for us");
    expect(html).not.toContain("Beyond what we can offer");
    expect(html).toContain("Not measured — Legal checks");
    expect(matches(c, "NEGATIVE", list)).toBe(false);
    expect(offerFor(c, [POINT])).toBeNull();
  });

  it("says a missing point is not in their paper", () => {
    expect(renderToStaticMarkup(<ForUs effect="NEGATIVE" measured="ABSENT" />)).toContain("Not in their paper");
  });

  it("keeps worse for what the server measured worse", () => {
    const c = theirs({ measured: "WORSE" });
    expect(renderToStaticMarkup(<ForUs effect="NEGATIVE" measured="WORSE" />)).toContain("Worse for us");
    expect(matches(c, "NEGATIVE", list)).toBe(true);
    expect(offerFor(c, [POINT])?.within).toBe(false);
  });
});

describe("a point nothing confirmed in one clause", () => {
  it("lists the clauses that may hold it, unranked, with no passage", () => {
    const html = card(theirs());
    expect(html).toContain("We could not tell which clause covers this. Clauses that may: 7 Assignment; 12 Taxes.");
  });

  it("names a restarted number by the heading it sits under", () => {
    expect(where(theirs({ clause: { number: "2", heading: null, under: "INVOICING AND PAYMENT" } })))
      .toBe("2 (INVOICING AND PAYMENT)");
  });
});

describe("the Changes tab on one version", () => {
  const v = (over: Partial<DocumentVersion>) => ({ id: "v1", version_number: 1, ...over }) as DocumentVersion;
  it("opens on a single undeclared version, as the server lists it", () => {
    expect(changesEnabled([v({})])).toBe(true);
    expect(changesEnabled([v({ version_role: "CLIENT_MODIFIED" })])).toBe(true);
  });
  it("stays shut on our own single draft, and with no version at all", () => {
    expect(changesEnabled([v({ version_role: "COMPANY_DRAFT" })])).toBe(false);
    expect(changesEnabled([v({ source: "ORGANIZATION" })])).toBe(false);
    expect(changesEnabled([v({ version_role: "COMPANY_DRAFT",
                                 made_from_template: { template_key: "t", version: 1, older: false, message: null } })])).toBe(true);
    expect(changesEnabled([])).toBe(false);
  });
});
