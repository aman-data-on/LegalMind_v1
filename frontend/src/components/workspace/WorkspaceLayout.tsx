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

export type Region = "document" | "findings" | "analysis";
type Mode = "wide" | "one";
type SideTab = "analysis" | "findings";

/*
 * ⚠️ "Analysis", NOT "AI Analysis" — renamed 2026-09-01.
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
  analysis: "Analysis",
};

/** Lets the Analysis panel's "View all" open the Findings tab. */
const SideTabCtx = createContext<{ openFindings: () => void } | null>(null);
export function useSideTabs() {
  return useContext(SideTabCtx);
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
  const [tab, setTab] = useState<Region>("document");
  const [sideTab, setSideTab] = useState<SideTab>(initialSideTab);
  const tabsRef = useRef<HTMLDivElement | null>(null);
  const sideTabsRef = useRef<HTMLDivElement | null>(null);

  const openFindings = useCallback(() => {
    setSideTab("findings");
    setTab("findings");
  }, []);
  const sideCtx = useMemo(() => ({ openFindings }), [openFindings]);

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
      <div className="ws-workspace ws-workspace--wide" data-mode="wide">
        <section className="ws-pane ws-pane--document" aria-label="Document" data-region="document">
          {document}
        </section>
        <section className="ws-pane ws-pane--side" aria-label="Analysis and findings">
          <div className="ws-side__tabs" role="tablist" aria-label="Analysis views" ref={sideTabsRef}>
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
