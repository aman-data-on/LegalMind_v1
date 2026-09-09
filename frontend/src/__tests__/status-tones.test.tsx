/**
 * One colour system for the three reader words, and one order — owner
 * instruction, 2026-09-09:
 *
 *   Acceptable             green   (`--ws-ok`,   tone `ok`)
 *   Requires modification  amber   (`--ws-warn`, tone `warn`)
 *   Needs a decision       red     (`--ws-bad`,  tone `bad`)
 *
 * The amber and the red were the wrong way round: "Requires modification"
 * inherited the loud red treatment (a solid chip and a red card edge) from the
 * status `AM-56` renamed away, while "Needs a decision" — the one word that
 * says the engine could not determine acceptance at all — wore amber. Five
 * surfaces spelled the mapping out for themselves, so putting it right in one
 * of them would have left the others disagreeing.
 *
 * This asserts the RENDERED tone class and the RENDERED order on the Summary's
 * tiles, bar and ring legend, and on a finding card — not the constants, which
 * would only restate themselves. The Dashboard badges and the browser view are
 * covered in `e2e/journey.spec.ts` and `e2e/workspace.spec.ts`.
 *
 * `renderToStaticMarkup` in the house idiom: no DOM, no testing library.
 */

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { FindingCard } from "@/components/workspace/FindingsPane";
import { AnalysisPanel } from "@/components/workspace/AnalysisPanel";
import { HighlightProvider } from "@/components/workspace/highlight";
import {
  USER_STATUS_LABELS,
  USER_STATUS_ORDER,
  USER_STATUS_TONE,
} from "@/components/workspace/findingLanguage";
import type { Evaluation, Finding, Review, UserStatusWord } from "@/lib/types";

vi.mock("@/lib/session", () => ({
  useSession: () => ({ can: (permission: string) => permission === "finding.view" }),
  useSeesLegalPosition: () => false,
}));
vi.mock("@/components/workspace/WorkspaceLayout", () => ({ useSideTabs: () => null }));
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

/** One of each word, so every tone has to appear exactly once. */
const FINDINGS: Finding[] = [
  finding("f1", "CONFLICT", "NEEDS_DECISION"),
  finding("f2", "MATCH", "ACCEPTABLE"),
  finding("f3", "DEVIATION", "REQUIRES_MODIFICATION"),
];

function summary(findings: Finding[] = FINDINGS): string {
  loaded = findings;
  return renderToStaticMarkup(
    <HighlightProvider>
      <AnalysisPanel documentVersionId="v1" />
    </HighlightProvider>,
  );
}

function card(f: Finding): string {
  return renderToStaticMarkup(
    <HighlightProvider>
      <FindingCard finding={f} onChanged={() => {}} prepared={null} explanation={null} />
    </HighlightProvider>,
  );
}

/** Every occurrence of `prefix<tone>`, in render order. */
function tones(html: string, prefix: string): string[] {
  return Array.from(html.matchAll(new RegExp(`${prefix}(ok|warn|bad)`, "g"))).map((m) => m[1]!);
}

const EXPECTED = ["ok", "warn", "bad"];

describe("the three reader words wear one tone each, in one order", () => {
  it("declares green Acceptable, amber Requires modification, red Needs a decision", () => {
    // The order and the tone travel together — this is the pair every surface
    // below reads, and the one thing a future change should have to edit.
    expect(USER_STATUS_ORDER.map((s) => [USER_STATUS_LABELS[s], USER_STATUS_TONE[s]])).toEqual([
      ["Acceptable", "ok"],
      ["Requires modification", "warn"],
      ["Needs a decision", "bad"],
    ]);
  });

  it("puts the Summary tiles in that order, each in its own tone", () => {
    const html = summary();
    expect(tones(html, "ws-tile--")).toEqual(EXPECTED);
    // The label order matches the tone order — a tile cannot wear one word and
    // another word's colour.
    expect(Array.from(html.matchAll(/ws-tile__label">([^<]+)</g)).map((m) => m[1]))
      .toEqual(["Acceptable", "Requires modification", "Needs a decision"]);
  });

  it("puts the proportion bar and the ring legend in the same order and tones", () => {
    const html = summary();
    expect(tones(html, "ws-bar__seg--")).toEqual(EXPECTED);
    expect(tones(html, 'data-tone="')).toEqual(EXPECTED);
    expect(tones(html, "ws-ring__seg--")).toEqual(EXPECTED);
  });

  it("keeps the order when a word has no findings", () => {
    const html = summary([FINDINGS[0]!, FINDINGS[2]!]); // no Acceptable
    expect(tones(html, "ws-tile--")).toEqual(["warn", "bad"]);
    expect(tones(html, "ws-bar__seg--")).toEqual(["warn", "bad"]);
  });

  it("marks a Requires modification card amber and a Needs a decision card red", () => {
    expect(tones(card(FINDINGS[2]!), "ws-finding__mark--")).toEqual(["warn"]);
    expect(tones(card(FINDINGS[0]!), "ws-finding__mark--")).toEqual(["bad"]);
    expect(tones(card(FINDINGS[1]!), "ws-finding__mark--")).toEqual(["ok"]);
  });

  it("gives the loud solid chip to Needs a decision, not to Requires modification", () => {
    // The chip class carries the status, and the stylesheet gives
    // `--status-needs_decision` the solid red fill. Asserted as the class the
    // card renders, since a static render cannot read the stylesheet.
    expect(card(FINDINGS[0]!)).toContain("ws-chip--status-needs_decision");
    expect(card(FINDINGS[2]!)).toContain("ws-chip--status-requires_modification");
  });

  it("never shows a tone without its word", () => {
    // Rule 12 and DESIGN.md: colour is never the only carrier. Every tone that
    // renders on a tile has its label beside it.
    const html = summary();
    for (const status of USER_STATUS_ORDER) expect(html).toContain(USER_STATUS_LABELS[status]);
  });
});
