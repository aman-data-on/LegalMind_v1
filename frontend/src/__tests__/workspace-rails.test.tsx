/**
 * The document workspace's two right rails and citations that land in the document
 * (owner, 2026-10-08): "citation links (clicking one should jump to and highlight that
 * part of the document), two separate sidebars on the right (Talk, and
 * Summary/Findings)". Static render, the house idiom; the scroll and the light itself
 * are the highlight gesture's own, pinned by the browser suite.
 */
import { readFileSync } from "node:fs";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { AnswerProse } from "@/components/workspace/AnswerProse";
import { AskDock, showInOpenDocument } from "@/components/workspace/AskDock";
import { HighlightProvider } from "@/components/workspace/highlight";
import { SideTabCtx, WorkspaceLayout } from "@/components/workspace/WorkspaceLayout";
import type { AskSource } from "@/lib/types";

const clause: AskSource = {
  key: "D58", kind: "document", location: "13.1", scope: "the selected document",
  text: "13.1 The total liability of the provider shall in no case exceed …",
  evidence_id: "ev-58", document_version_id: "dv-2",
};
const answer = { document_version_id: "dv-2" };

describe("a cited clause of this agreement is shown in the open document", () => {
  it("points the workspace highlight at the clause's evidence row", () => {
    const point = vi.fn();
    showInOpenDocument(answer, false, point)(clause)?.();
    // `true`: the passage itself, lit in the Text view even when the PDF is open
    expect(point).toHaveBeenCalledWith("ev-58", "source D58", true);
  });

  it("offers nothing it cannot land: another version, another document, a standard", () => {
    const point = vi.fn();
    const show = showInOpenDocument(answer, false, point);
    expect(show({ ...clause, document_version_id: "dv-1" })).toBeUndefined();
    expect(show({ ...clause, scope: "MSA with another customer" })).toBeUndefined();
    const { evidence_id: _, ...noRow } = clause;
    expect(show({ ...noRow, kind: "position" })).toBeUndefined();
    expect(show(noRow)).toBeUndefined();
    // the answer itself was read from another version than the one open
    expect(showInOpenDocument(answer, true, point)(clause)).toBeUndefined();
  });

  it("names the marker for what it does; without the dock it still goes to the source", () => {
    const text = "The cap is three months' fees. [D58]\n\nSources\n\n- D58: 13.1, the selected document";
    const docked = renderToStaticMarkup(
      <AnswerProse text={text} sources={[clause]} showInDocument={() => () => undefined} />);
    expect(docked).toContain('aria-label="Show source D58 in the document"');
    const plain = renderToStaticMarkup(<AnswerProse text={text} sources={[clause]} />);
    expect(plain).toContain('aria-label="Go to source D58"');
    expect(plain).not.toContain("in the document\"");
  });
});

function dock(ctx: Partial<React.ContextType<typeof SideTabCtx> & object> = {}) {
  return renderToStaticMarkup(
    <HighlightProvider>
      <SideTabCtx.Provider value={{ openFindings: () => {}, findingsPoint: null, closeAskSeq: 0,
                                    askRail: false, ...ctx }}>
        <AskDock contractId="c-1" documentVersionId="dv-2" versionNumber={2} isLatest />
      </SideTabCtx.Provider>
    </HighlightProvider>,
  );
}

describe("Ask in its own column", () => {
  it("is shown open with no launcher, and its close folds the column back into the row", () => {
    const html = dock({ askRail: true, askOpen: true, setAskOpen: () => {} });
    expect(html).toContain('data-open="true"');
    expect(html).toMatch(/class="ws-dock__launcher"[^>]*hidden/);
    expect(html).toContain('aria-label="Close Ask"');
    expect(html).toContain('id="ws-pane-ask"');
  });

  it("stays the launcher-and-close disclosure where nothing controls it (narrow screens)", () => {
    const html = dock();
    expect(html).toContain('data-open="false"');
    expect(html).not.toMatch(/class="ws-dock__launcher"[^>]*hidden/);
    expect(html).toContain('aria-label="Close Ask"');
  });

  it("gives the document, Summary/Findings and Ask a column each from 1680px", () => {
    const css = readFileSync("src/app/dashboard/workspace.css", "utf8");
    expect(css).toMatch(/\.ws-workspace--wide\[data-ask-rail\]\[data-doc-open="true"\] \{\s*grid-template-columns: minmax\(0, 1fr\) var\(--ws-side-w\) var\(--ws-ask-w\);/);
    const layout = readFileSync("src/components/workspace/WorkspaceLayout.tsx", "utf8");
    expect(layout).toContain("const ASK_RAIL_MIN = 1680;");
  });
});

describe("the side card's tab row (owner, 2026-10-08)", () => {
  function layout() {
    return renderToStaticMarkup(
      <HighlightProvider>
        <WorkspaceLayout document={<p>doc</p>} findings={<p>findings</p>} analysis={<p>summary</p>}
          ask={<AskDock contractId="c-1" documentVersionId="dv-2" versionNumber={2} isLatest />} />
      </HighlightProvider>,
    );
  }

  it("carries Ask as the third tab beside Summary and Findings, controlling the dock", () => {
    const html = layout();
    expect(html).toMatch(/role="tab" id="ws-tab-ask" aria-selected="false" aria-controls="ws-pane-ask"/);
    // The dock itself is placed once the viewport is measured — never on the server,
    // where it would mount in one column and remount in the other a frame later.
    expect(html).not.toContain("ws-dock");
  });

  it("shows or hides the document with the Contents panel's own icon, named in words", () => {
    const html = layout();
    expect(html).toMatch(/class="ws-outline__collapse ws-side__doctoggle"[^>]*aria-label="Show document"[^>]*title="Show document"/);
    expect(html).not.toContain(">Show document<");
    expect(html).not.toContain(">Hide document<");
  });
});
