"use client";

/**
 * Three regions — document · findings · analysis — that collapse to tabs, never
 * to a dropped region (DESIGN.md § Responsive: a collapsed pane is a labelled
 * tab; state is never silently lost).
 *
 *   ≥ 1280px  three panes side by side
 *   ≥ 900px   document + one tabbed secondary pane
 *   below     one pane at a time, all three as tabs
 *
 * Ask is deliberately NOT a region any more (2026-08-31 redesign): it lives in
 * the sticky AskBar below the grid, mounted at every breakpoint, so it is
 * reachable regardless of scroll position or active tab — which also retires
 * the old "switch to the Ask tab when a draft arrives" effect.
 *
 * Real tab semantics (role=tablist/tab/tabpanel, aria-selected, arrow keys), so
 * the collapsed state is as operable from a keyboard as the wide one.
 */

import { useEffect, useRef, useState } from "react";

export type Region = "document" | "findings" | "analysis";
type Mode = "three" | "two" | "one";

const LABEL: Record<Region, string> = {
  document: "Document",
  findings: "Findings",
  analysis: "AI Analysis",
};

function useMode(): Mode {
  const [mode, setMode] = useState<Mode>("three");
  useEffect(() => {
    const wide = window.matchMedia("(min-width: 1280px)");
    const mid = window.matchMedia("(min-width: 900px)");
    const apply = () => setMode(wide.matches ? "three" : mid.matches ? "two" : "one");
    apply();
    wide.addEventListener("change", apply);
    mid.addEventListener("change", apply);
    return () => {
      wide.removeEventListener("change", apply);
      mid.removeEventListener("change", apply);
    };
  }, []);
  return mode;
}

export function WorkspaceLayout({
  document,
  findings,
  analysis,
}: Record<Region, React.ReactNode>) {
  const mode = useMode();
  const [tab, setTab] = useState<Region>("findings");
  const tabsRef = useRef<HTMLDivElement | null>(null);

  const panes: Record<Region, React.ReactNode> = { document, findings, analysis };
  const tabbed: Region[] = mode === "one" ? ["document", "findings", "analysis"] : ["findings", "analysis"];
  const visible: Region[] =
    mode === "three" ? ["document", "findings", "analysis"]
    : mode === "two" ? ["document", tab === "document" ? "findings" : tab]
    : [tab];

  function onTabKey(event: React.KeyboardEvent, index: number) {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    const next = (index + (event.key === "ArrowRight" ? 1 : -1) + tabbed.length) % tabbed.length;
    setTab(tabbed[next]!);
    tabsRef.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[next]?.focus();
    event.preventDefault();
  }

  return (
    <>
      {mode !== "three" ? (
        <div className="ws-tabs" role="tablist" aria-label="Workspace regions" ref={tabsRef}>
          {tabbed.map((region, index) => {
            const selected = visible.includes(region) && region !== "document" || (mode === "one" && tab === region);
            return (
              <button
                key={region}
                type="button"
                role="tab"
                id={`ws-tab-${region}`}
                aria-selected={selected}
                aria-controls={`ws-pane-${region}`}
                tabIndex={selected ? 0 : -1}
                onClick={() => setTab(region)}
                onKeyDown={(event) => onTabKey(event, index)}
              >
                {LABEL[region]}
              </button>
            );
          })}
        </div>
      ) : null}
      <div className={`ws-workspace ws-workspace--${mode}`} data-mode={mode}>
        {visible.map((region) => (
          <section
            key={region}
            className="ws-pane"
            id={`ws-pane-${region}`}
            role={mode !== "three" && region !== "document" ? "tabpanel" : undefined}
            aria-labelledby={mode !== "three" && region !== "document" ? `ws-tab-${region}` : undefined}
            aria-label={mode === "three" || region === "document" ? LABEL[region] : undefined}
            data-region={region}
          >
            {panes[region]}
          </section>
        ))}
      </div>
    </>
  );
}
