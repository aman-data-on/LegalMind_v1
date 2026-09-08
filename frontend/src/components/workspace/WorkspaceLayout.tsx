"use client";

/**
 * The reference-matched workspace shape (owner, 2026-09-01): the document area
 * (clauses card + document card) with ONE side card whose header is a small
 * tab pair — **Analysis** (default) and **Findings**. The reference design
 * has no separate findings column; the full findings pane — decisions,
 * escalation, the legal core — lives one tab away, never hidden behind a
 * scroll or a page change, and a `?finding=` / `?classification=` deep link
 * opens it directly.
 *
 *   ≥ 900px   document area + side card (internal tabs)
 *   below     one region at a time, all three as top tabs
 *
 * Both side panes stay MOUNTED (hidden with the `hidden` attribute), so tab
 * switches never lose state and the shared findings poll keeps running.
 * Real tab semantics (role=tablist/tab/tabpanel, aria-selected, arrow keys).
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { KeyboardShortcutsHelp } from "@/components/KeyboardShortcuts";

import { useHighlight } from "./highlight";
import { useWorkspaceShortcuts } from "./useWorkspaceShortcuts";

export type Region = "document" | "findings" | "analysis";
type Mode = "wide" | "one";
type SideTab = "analysis" | "findings";

/**
 * How the wide workspace divides itself — owner request, 2026-09-08.
 *
 * THE PROBLEM. The document held the centre of the screen permanently and the
 * whole of the analysis lived in a 380px rail beside it (340px below 1440px).
 * For most of the people who open a review — Sales, Customer Success,
 * management — the document is not the task: the findings are, and they were
 * the narrowest thing on screen. It is also why a finding's heading rendered
 * one letter per line: 380px minus padding is not a column a heading, three
 * chips and a comparison can share.
 *
 * `review` gives the findings the width and keeps the document one click away
 * with its state intact; `split` is the previous layout, which is the right one
 * when the job IS reading the document. Two states rather than a resizable
 * splitter and three named modes: the document already takes the majority in
 * `split`, so a third "document" mode would only have removed the findings.
 *
 * Pointing at evidence switches to `split` on its own (see the effect below) —
 * a citation click has to end with the passage visible, and asking the reader
 * to reveal the document first would break the workspace's signature gesture.
 */
type Focus = "review" | "split";
const FOCUS_KEY = "legalmind.workspace.focus";

/*
 * ⚠️ Never "AI Analysis" (renamed 2026-09-01). The default tab is labelled
 * **Summary** since the 2026-09-04 audit: "Analysis | Findings" read as two
 * different analyses, and the word is overloaded — it is also the pipeline and
 * the Review's own state. Summary and Findings are a whole and its parts, which
 * is the relationship a reader actually needs to grasp.
 *
 * The owner's reference labelled this tab "AI ANALYSIS". Everything in it except
 * Key Obligations is the output of the DETERMINISTIC evaluator: the status
 * summary, the clause breakdown and the findings awaiting a decision all come
 * from rule evaluation against a ratified Company Standard, with no model
 * anywhere near them. `AI-01` (reaffirmed by `AM-25`) keeps every LLM, RAG,
 * embedding and vector store OUT of that path.
 *
 * So the label was not just imprecise, it was backwards: it credited a model for
 * the one part of the product whose value is that no model touched it — and it
 * would invite a reader to discount a Finding as "the AI's opinion" when it is a
 * reproducible rule outcome. The assist lane's own contributions are labelled
 * where they appear (Key Obligations, Ask), which is where the distinction
 * belongs.
 */
const LABEL: Record<Region, string> = {
  document: "Document",
  findings: "Findings",
  analysis: "Summary",
};

/**
 * What an Analysis-panel click asks the Findings pane to show (2026-09-02,
 * DD-14 — every analysis card navigates somewhere real): a classification
 * filter, a specific finding, or neither (just the tab). `seq` makes each
 * request distinct so clicking the same tile twice still re-points.
 */
export interface FindingsPoint {
  classification?: string;
  findingId?: string;
  seq: number;
}

/** Lets the Analysis panel open the Findings tab, optionally pointed. */
const SideTabCtx = createContext<{
  openFindings: (target?: Omit<FindingsPoint, "seq">) => void;
  findingsPoint: FindingsPoint | null;
} | null>(null);
export function useSideTabs() {
  return useContext(SideTabCtx);
}

/**
 * The reader's own last choice, remembered per browser.
 *
 * A layout preference is exactly what `localStorage` is for — it is this
 * viewer's convenience, it never needs to reach the server, and losing it
 * costs one click. Every access is guarded: a private window, cleared site
 * data or a browser set to block storage all throw on read, and the workspace
 * must render regardless.
 */
function storedFocus(): Focus {
  try {
    return window.localStorage.getItem(FOCUS_KEY) === "split" ? "split" : "review";
  } catch {
    return "review";
  }
}

function useMode(): Mode {
  const [mode, setMode] = useState<Mode>("wide");
  useEffect(() => {
    const mid = window.matchMedia("(min-width: 900px)");
    const apply = () => setMode(mid.matches ? "wide" : "one");
    apply();
    mid.addEventListener("change", apply);
    return () => mid.removeEventListener("change", apply);
  }, []);
  return mode;
}

/** A deep link into a finding or a classification filter must land on the
 *  findings view, not behind the analysis tab. */
function initialSideTab(): SideTab {
  if (typeof window === "undefined") return "analysis";
  const params = new URLSearchParams(window.location.search);
  return params.get("finding") || params.get("classification") ? "findings" : "analysis";
}

export function WorkspaceLayout({
  document,
  findings,
  analysis,
}: Record<Region, React.ReactNode>) {
  const mode = useMode();
  /* Above the narrow-mode early return below: a hook after a conditional return
     runs on some renders and not others, which is React error #310 — and it
     showed up as the collapsed layout rendering no tabs at all. */
  const shortcuts = useWorkspaceShortcuts();
  const [tab, setTab] = useState<Region>("document");
  const [focus, setFocus] = useState<Focus>("review");
  // Read after mount, never during render: the server has no `localStorage`,
  // and reading it in a `useState` initialiser is a hydration mismatch.
  useEffect(() => { setFocus(storedFocus()); }, []);
  const chooseFocus = useCallback((next: Focus) => {
    setFocus(next);
    try {
      window.localStorage.setItem(FOCUS_KEY, next);
    } catch {
      // A viewer who blocks storage keeps the choice for this visit only.
    }
  }, []);
  /* Pointing at evidence reveals the document. `target` is the workspace's one
     "look at this passage" signal — a citation, an outline entry, a verdict or
     a `?evidence=` link all set it — so this is the single place that has to
     answer, rather than every call site remembering to. The finding stays
     exactly where it is: both panes are mounted in this layout, so nothing is
     unmounted and nothing is re-fetched. */
  const { target } = useHighlight();
  useEffect(() => {
    if (target) setFocus("split");
  }, [target]);
  const [sideTab, setSideTab] = useState<SideTab>(initialSideTab);
  const [findingsPoint, setFindingsPoint] = useState<FindingsPoint | null>(null);
  const tabsRef = useRef<HTMLDivElement | null>(null);
  const sideTabsRef = useRef<HTMLDivElement | null>(null);

  const openFindings = useCallback((target?: Omit<FindingsPoint, "seq">) => {
    setSideTab("findings");
    setTab("findings");
    if (target) setFindingsPoint((p) => ({ ...target, seq: (p?.seq ?? 0) + 1 }));
  }, []);
  const sideCtx = useMemo(() => ({ openFindings, findingsPoint }), [openFindings, findingsPoint]);

  // ---- narrow: one region at a time, top tabs -----------------------------
  const tabbed: Region[] = ["document", "findings", "analysis"];

  function onTabKey(event: React.KeyboardEvent, index: number) {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    const next = (index + (event.key === "ArrowRight" ? 1 : -1) + tabbed.length) % tabbed.length;
    setTab(tabbed[next]!);
    tabsRef.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[next]?.focus();
    event.preventDefault();
  }

  if (mode === "one") {
    return (
      <SideTabCtx.Provider value={sideCtx}>
        {/* The sheet is mounted in BOTH layouts: a keyboard user on a narrow
            screen needs it at least as much as one on a wide screen. */}
        <KeyboardShortcutsHelp open={shortcuts.helpOpen} onClose={shortcuts.closeHelp} />
        <div className="ws-tabs" role="tablist" aria-label="Workspace regions" ref={tabsRef}>
          {tabbed.map((region, index) => (
            <button
              key={region}
              type="button"
              role="tab"
              id={`ws-tab-${region}`}
              aria-selected={tab === region}
              aria-controls={`ws-pane-${region}`}
              tabIndex={tab === region ? 0 : -1}
              onClick={() => setTab(region)}
              onKeyDown={(event) => onTabKey(event, index)}
            >
              {LABEL[region]}
            </button>
          ))}
        </div>
        <div className="ws-workspace ws-workspace--one" data-mode="one">
          <section
            className="ws-pane"
            id={`ws-pane-${tab}`}
            role="tabpanel"
            aria-labelledby={`ws-tab-${tab}`}
            data-region={tab}
          >
            {{ document, findings, analysis }[tab]}
          </section>
        </div>
      </SideTabCtx.Provider>
    );
  }

  // ---- wide: document area + the side card with internal tabs -------------
  const sideTabs: SideTab[] = ["analysis", "findings"];

  function onSideTabKey(event: React.KeyboardEvent, index: number) {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    const next = (index + (event.key === "ArrowRight" ? 1 : -1) + sideTabs.length) % sideTabs.length;
    setSideTab(sideTabs[next]!);
    sideTabsRef.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[next]?.focus();
    event.preventDefault();
  }

  return (
    <SideTabCtx.Provider value={sideCtx}>
      {/*
        * The shortcut layer, mounted once for the whole workspace (2026-09-04).
        * `?` opens the sheet from anywhere; `j`/`k` (`n`/`p`) walk the findings;
        * `/` reaches the document's find field. It lived only in the legacy
        * Review screen before this, so retiring those routes would have removed
        * a keyboard affordance rather than dead code.
        */}
      <KeyboardShortcutsHelp open={shortcuts.helpOpen} onClose={shortcuts.closeHelp} />
      <div className="ws-workspace ws-workspace--wide" data-mode="wide" data-focus={focus}>
        <section
          className="ws-pane ws-pane--document"
          aria-label="Document"
          data-region="document"
          /* `inert`, not unmounted: the pane keeps its scroll position, its
             Original/Text choice and its outline state, so revealing it returns
             the reader to where they were. `hidden` would take it out of the
             accessibility tree AND stop the scroll-to-evidence gesture from
             finding its rows, so the CSS hides it and `inert` keeps it out of
             the tab order while it is not shown. */
          inert={focus === "review" ? true : undefined}
        >
          {document}
        </section>
        <section className="ws-pane ws-pane--side" aria-label="Analysis and findings">
          <div className="ws-side__tabs">
            <div className="ws-side__tablist" role="tablist" aria-label="Analysis views" ref={sideTabsRef}>
            {sideTabs.map((which, index) => (
              <button
                key={which}
                type="button"
                role="tab"
                id={`ws-tab-${which}`}
                aria-selected={sideTab === which}
                aria-controls={`ws-pane-${which}`}
                tabIndex={sideTab === which ? 0 : -1}
                onClick={() => setSideTab(which)}
                onKeyDown={(event) => onSideTabKey(event, index)}
              >
                {LABEL[which]}
              </button>
            ))}
            </div>
            {/* The document, on request. A real toggle rather than a third tab:
                the document is not a view OF the analysis, it is the thing the
                analysis is about, and in `split` both are on screen at once —
                which no tab set can express. */}
            <button
              type="button"
              className="ws-side__doctoggle"
              aria-pressed={focus === "split"}
              onClick={() => chooseFocus(focus === "split" ? "review" : "split")}
            >
              {focus === "split" ? "Hide document" : "Show document"}
            </button>
          </div>
          <div
            className="ws-side__panel"
            id="ws-pane-analysis"
            role="tabpanel"
            aria-labelledby="ws-tab-analysis"
            data-region="analysis"
            hidden={sideTab !== "analysis"}
          >
            {analysis}
          </div>
          <div
            className="ws-side__panel"
            id="ws-pane-findings"
            role="tabpanel"
            aria-labelledby="ws-tab-findings"
            data-region="findings"
            hidden={sideTab !== "findings"}
          >
            {findings}
          </div>
        </section>
      </div>
    </SideTabCtx.Provider>
  );
}
