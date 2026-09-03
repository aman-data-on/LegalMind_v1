/**
 * The Ask dock — the floating, secondary Ask surface (DD-15, 2026-09-02) and the
 * version context it makes explicit.
 *
 * Two things are pinned here, and they are the two things the owner reported:
 *
 *  1. Ask reserves NO workspace height when closed, and is still reachable —
 *     a real button in the tab order, not a hover-only affordance.
 *  2. Ask is never disabled for reading an older version, and every answer says
 *     which version it was read from. A turn answered from a different version
 *     than the one on screen offers to open THAT version rather than pointing the
 *     highlight at an evidence row the open page does not contain.
 *
 * Static render, the house idiom. Live submission against a real refusing
 * backend stays in the browser suite.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { AskDock, WsAnswerView, turnsFromHistory } from "@/components/workspace/AskDock";
import { HighlightProvider } from "@/components/workspace/highlight";
import type { AskResult, ConversationTurn } from "@/lib/types";

function dock(props: Partial<Parameters<typeof AskDock>[0]> = {}) {
  return renderToStaticMarkup(
    <HighlightProvider>
      <AskDock
        contractId="c-1"
        documentVersionId="dv-2"
        versionNumber={2}
        isLatest
        {...props}
      />
    </HighlightProvider>,
  );
}

function result(overrides: Partial<AskResult>): AskResult {
  return {
    conversation_id: "c-1", message_id: "m-1", answer_state: "ANSWERED", text: "",
    routed_to_evaluator: false, document_version_id: "dv-2", version_number: 2,
    citations: [], ...overrides,
  };
}

const CITATION = {
  chunk_id: "ch-1", evidence_id: "ev-9", page_number: 7, section_ref: "22",
  excerpt: "Either party may terminate on ninety days prior written notice.",
  retrieval_score: 0.6213,
};

// =====================================================================
// Closed state — secondary, and costing no workspace height
// =====================================================================
describe("the closed dock", () => {
  it("is a compact launcher, not a permanent bar reserving the bottom of the workspace", () => {
    const html = dock();
    expect(html).toContain("ws-dock__launcher");
    // The bar that used to hold a permanent row is gone entirely.
    expect(html).not.toContain("ws-askbar");
  });

  it("is a real button in the tab order with an accessible name — never hover-only", () => {
    const html = dock();
    expect(html).toContain('type="button"');
    expect(html).toContain('aria-expanded="false"');
    expect(html).toContain("about this document");
    // No tabindex=-1 and no title-only affordance on the launcher.
    expect(html).not.toContain('class="ws-dock__launcher" tabindex="-1"');
  });

  it("declares what it controls, so the disclosure is programmatic and not visual only", () => {
    const html = dock();
    const controls = /aria-controls="([^"]+)"/.exec(html);
    expect(controls).not.toBeNull();
    expect(html).toContain(`id="${controls![1]}"`);
  });

  it("keeps the panel MOUNTED but inert, so a draft and the history survive closing", () => {
    const html = dock();
    expect(html).toContain("ws-dock__panel");
    expect(html).toContain('aria-hidden="true"');
    expect(html).toContain('data-open="false"');
  });

  it("renders no scrim while closed — the workspace stays fully usable", () => {
    expect(dock()).not.toContain("ws-dock__scrim");
  });
});

// =====================================================================
// Version context — the reported defect
// =====================================================================
describe("version context", () => {
  it("names the version answers are about, and offers no 'open the latest version' escape", () => {
    const html = dock({ documentVersionId: "dv-1", versionNumber: 1, isLatest: false });
    expect(html).toContain("Version 1");
    expect(html).toContain("the version you are reading");
    expect(html).not.toContain("Open the latest version");
  });

  it("does NOT disable the input when an older version is open — the whole point", () => {
    const older = dock({ documentVersionId: "dv-1", versionNumber: 1, isLatest: false });
    expect(older).toContain('id="ws-ask-question"');
    expect(older).not.toContain("disabled=\"\" id=\"ws-ask-question\"");
    // The placeholder is the ordinary invitation, not an explanation of a block.
    expect(older).toContain("Ask about this document…");
  });

  it("marks the latest version as latest, so the reader knows where they are", () => {
    expect(dock()).toContain("(latest)");
  });
});

// =====================================================================
// Citations across versions
// =====================================================================
describe("a citation from another version", () => {
  const render = (r: AskResult, openVersionNumber?: number) =>
    renderToStaticMarkup(
      <HighlightProvider>
        <WsAnswerView
          result={r}
          openVersionNumber={openVersionNumber}
          onOpenVersion={() => {}}
        />
      </HighlightProvider>,
    );

  it("points at its evidence row normally when the answer matches the open version", () => {
    const html = render(result({ text: "Ninety days [1].", citations: [CITATION] }), 2);
    expect(html).toContain('data-evidence-id="ev-9"');
    expect(html).not.toContain("data-other-version");
    expect(html).not.toContain("open Version");
  });

  it("offers to open the answer's own version instead of a highlight that cannot land", () => {
    const html = render(
      result({ text: "Ninety days [1].", citations: [CITATION],
               document_version_id: "dv-1", version_number: 1 }),
      2,
    );
    // An evidence row belongs to one version's reading order: pointing at it on
    // the wrong page moves nothing while announcing that it did.
    expect(html).toContain('data-other-version="1"');
    expect(html).toContain("open Version 1");
  });

  it("still shows the excerpt and the labelled retrieval score — never a confidence", () => {
    const html = render(
      result({ text: "Ninety days [1].", citations: [CITATION],
               document_version_id: "dv-1", version_number: 1 }),
      2,
    );
    expect(html).toContain("ninety days prior written notice");
    expect(html).toContain("retrieval score 0.621");
    expect(html.toLowerCase()).not.toContain("confidence");
  });

  it("leaves refusals and evaluator-routed replies untouched by any of this", () => {
    const refusal = render(result({
      answer_state: "NO_EVIDENCE_RETRIEVED", text: "Information not found in the selected document.",
      document_version_id: "dv-1", version_number: 1,
    }), 2);
    expect(refusal).toContain("ws-ask__answer--refusal");
    expect(refusal).not.toContain("open Version");

    const routed = render(result({
      routed_to_evaluator: true, text: "That is a Findings question.",
      document_version_id: "dv-1", version_number: 1,
    }), 2);
    expect(routed).toContain("ws-ask__answer--routed");
    expect(routed).not.toContain("open Version");
  });
});

// =====================================================================
// Replay — a transcript may legitimately span versions
// =====================================================================
describe("turnsFromHistory", () => {
  const turn = (o: Partial<ConversationTurn>): ConversationTurn => ({
    id: "m", ordinal: 0, role: "USER", content: "", answer_state: null,
    routed_to_evaluator: false, document_version_id: null, version_number: null,
    citations: [], ...o,
  });

  it("carries each answer's own version through to the rendered turn", () => {
    const turns = turnsFromHistory([
      turn({ id: "q1", ordinal: 0, role: "USER", content: "notice period?" }),
      turn({ id: "a1", ordinal: 1, role: "ASSISTANT", content: "Ninety days [1].",
             answer_state: "ANSWERED", document_version_id: "dv-1", version_number: 1 }),
      turn({ id: "q2", ordinal: 2, role: "USER", content: "and now?" }),
      turn({ id: "a2", ordinal: 3, role: "ASSISTANT", content: "Thirty days [1].",
             answer_state: "ANSWERED", document_version_id: "dv-2", version_number: 2 }),
    ]);
    expect(turns.map((t) => t.versionNumber)).toEqual([1, 2]);
    expect(turns.map((t) => t.documentVersionId)).toEqual(["dv-1", "dv-2"]);
    expect(turns.map((t) => t.result?.version_number)).toEqual([1, 2]);
  });

  it("keeps a turn with no version as null rather than defaulting it to something", () => {
    const turns = turnsFromHistory([
      turn({ id: "q", ordinal: 0, role: "USER", content: "does this meet our standard?" }),
      turn({ id: "a", ordinal: 1, role: "ASSISTANT", content: "That is a Findings question.",
             answer_state: "EVIDENCE_INSUFFICIENT", routed_to_evaluator: true }),
    ]);
    expect(turns).toHaveLength(1);
    expect(turns[0]!.versionNumber).toBeNull();
    expect(turns[0]!.documentVersionId).toBeNull();
  });

  it("drops an orphan assistant turn rather than inventing a question for it", () => {
    expect(turnsFromHistory([
      turn({ id: "a", ordinal: 0, role: "ASSISTANT", content: "x", answer_state: "ANSWERED" }),
    ])).toEqual([]);
  });
});
