/**
 * The Findings filter row — its ORDER, which is the point of the test.
 *
 * Owner instruction, 2026-09-09: the row reads "All" first and selected, then
 * the three reader words of `AM-56` in their own fixed order — Acceptable,
 * Requires modification, Needs a decision. It had grown the other way round:
 * a separate requires_decision filter came first and pushed "All" second, so
 * the row a reader learned on one contract was not the row the next contract
 * gave them, and the pane opened pre-filtered to a subset nobody chose.
 *
 * Nothing here sorts on the counts, and that is exactly what is asserted — an
 * order that reshuffles when the data changes is the bug this pins shut. The
 * counts themselves stay derived from the loaded findings' server-sent
 * `user_status` (52.7): presentation groups server values, it never re-derives
 * one.
 *
 * `renderToStaticMarkup` in the house idiom (see `finding-card.test.tsx`): no
 * DOM, no testing library — adding one is a rule 19 dependency decision. That
 * covers the row as rendered and the default view; clicking a filter and
 * seeing the subset is Playwright's job and lives in `e2e/journey.spec.ts`.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { FindingsPane } from "@/components/workspace/FindingsPane";
import { HighlightProvider } from "@/components/workspace/highlight";
import type { DocumentVersion, Evaluation, Finding, Review, UserStatusWord } from "@/lib/types";

// The pane needs three contexts it cannot get without a browser: the session
// (permission gating only — presentation, per rule 18), the shared findings
// state machine, and the side-tab pointer. `finding.view` alone, so the
// decision controls stay out of a test about a filter row.
vi.mock("@/lib/session", () => ({
  useSession: () => ({ can: (permission: string) => permission === "finding.view" }),
  useSeesLegalPosition: () => false,
}));
vi.mock("@/components/workspace/WorkspaceLayout", () => ({ useSideTabs: () => null }));
// The findings under test, swapped per case. Read when the hook is CALLED, so
// the mock factory (hoisted above this file's own statements) is fine.
let loaded: Finding[] = [];
vi.mock("@/components/workspace/findingsState", () => ({
  useFindingsState: () => ({
    state: { kind: "ready", review: REVIEW, findings: loaded },
    reload: () => {},
  }),
  useFindingsStateOptional: () => null,
}));

const REVIEW: Review = {
  id: "r1", contract_id: "c1", document_version_id: "v1",
  configuration_snapshot_id: "snap0000-0000-0000-0000-000000000000",
  status: "COMPLETED", created_by: "u1", created_at: null, started_at: null,
  completed_at: null, document_name: "MSA", document_type: "MSA",
  document_accessible: true,
};

function finding(id: string, classification: string, user_status: UserStatusWord): Finding {
  const evaluation = {
    id: `e-${id}`, finding_id: id, scope_key: "GENERAL", scope_label: null,
    evaluation_kind: "PRIMARY", classification,
    actual_value: { presence: "ABSENT" }, evaluated_facts: null,
    evidence_refs: [], diagnostics: [], evaluator_type: "PRESENCE",
    evaluator_version: "PRESENCE-v1", requires_decision: false,
    current_decision: null, created_at: null,
    expected_value: { presence: "PRESENT" }, rule_outcome: "NOT_APPLICABLE",
    explanation: [],
  } as Evaluation;
  return {
    id, review_id: "r1",
    requirement: { code: "LIABILITY-MSA-001", name: "LIABILITY-MSA-001", version_id: "rv1", version_number: 1 },
    classification, status: "OPEN", requires_decision: false, escalated: false,
    user_status, evaluations: [evaluation], evidence: [],
    created_at: null, updated_at: null,
  } as Finding;
}

/** Two Acceptable, three Requires modification, one Needs a decision — six
 *  findings whose three counts are all different, so a row that mixed two of
 *  them up could not pass by coincidence. */
const FINDINGS: Finding[] = [
  finding("f1", "MATCH", "ACCEPTABLE"),
  finding("f2", "DEVIATION", "REQUIRES_MODIFICATION"),
  finding("f3", "CONFLICT", "NEEDS_DECISION"),
  finding("f4", "MISSING", "REQUIRES_MODIFICATION"),
  finding("f5", "MATCH", "ACCEPTABLE"),
  finding("f6", "DEVIATION", "REQUIRES_MODIFICATION"),
];

function pane(findings: Finding[] = FINDINGS): string {
  loaded = findings;
  return renderToStaticMarkup(
    <HighlightProvider>
      <FindingsPane version={{ id: "v1", contract_id: "c1", version_number: 1 } as DocumentVersion} />
    </HighlightProvider>,
  );
}

/** The filter row's buttons, in the order they render. */
function filterRow(html: string): { label: string; pressed: boolean }[] {
  const row = html.match(/aria-label="Filter findings"[^>]*>(.*?)<\/div>/s);
  expect(row, "the filter row renders").toBeTruthy();
  return Array.from((row?.[1] ?? "").matchAll(/<button[^>]*>(.*?)<\/button>/gs))
    .map((m) => ({
      label: (m[1] ?? "").replace(/<[^>]*>/g, "").replace(/&#x27;|&quot;/g, "'").trim(),
      pressed: /aria-pressed="true"/.test(m[0]),
    }));
}

describe("the Findings filter row is one fixed order (owner, 2026-09-09)", () => {
  it("reads All, Acceptable, Requires modification, Needs a decision — in that order", () => {
    expect(filterRow(pane()).map((b) => b.label)).toEqual([
      "All (6)",
      "Acceptable (2)",
      "Requires modification (3)",
      "Needs a decision (1)",
    ]);
  });

  it("opens on All, so the reader lands on every finding", () => {
    const html = pane();
    const row = filterRow(html);
    expect(row[0]?.label).toMatch(/^All /);
    expect(row.filter((b) => b.pressed).map((b) => b.label)).toEqual(["All (6)"]);
    // Every finding is on screen under All, not a pre-filtered subset.
    expect(html.match(/data-finding-id=/g) ?? []).toHaveLength(6);
  });

  it("carries no second decision filter beside the status word", () => {
    // The old row had both a requires_decision filter reading "Needs decision
    // (n)" and — once AM-56 renamed the third status — a "Needs a decision (n)"
    // status filter: two buttons, almost one label. The legal-decision count
    // lives on the Summary as its own line instead.
    const labels = filterRow(pane()).map((b) => b.label);
    expect(labels.filter((l) => /decision/i.test(l))).toEqual(["Needs a decision (1)"]);
  });

  it("keeps the order when the data changes, and drops a word nothing carries", () => {
    // One MATCH and one CONFLICT: "Requires modification" has no findings, so
    // its button does not render — and the words that remain keep their places
    // rather than resorting on the counts.
    const labels = filterRow(pane([
      finding("f1", "CONFLICT", "NEEDS_DECISION"),
      finding("f2", "MATCH", "ACCEPTABLE"),
    ])).map((b) => b.label);
    expect(labels).toEqual(["All (2)", "Acceptable (1)", "Needs a decision (1)"]);
  });

  it("counts each word off the server's own user_status, never the classification", () => {
    // A server that calls a DEVIATION "Needs a decision" (an unruled one, say)
    // is followed, not corrected: the row groups server values (52.7).
    const labels = filterRow(pane([
      finding("f1", "DEVIATION", "NEEDS_DECISION"),
      finding("f2", "DEVIATION", "NEEDS_DECISION"),
    ])).map((b) => b.label);
    expect(labels).toEqual(["All (2)", "Needs a decision (2)"]);
  });
});
