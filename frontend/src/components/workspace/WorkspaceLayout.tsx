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

import { useStep } from "@/lib/nextStep";
import { FileText, GitCompareArrows, LayoutList, ListChecks, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { KeyboardShortcutsHelp } from "@/components/KeyboardShortcuts";

import { useHighlight } from "./highlight";
import { IconSparkle } from "./icons";
import { useWorkspaceShortcuts } from "./useWorkspaceShortcuts";

export type Region = "document" | "findings" | "analysis";
type Mode = "wide" | "one";
type SideTab = "analysis" | "findings";

/**
 * How the wide workspace divides itself — owner request, 2026-09-08, FIFTH
 * pass, reverting the fourth's arrangement while keeping its `docOpen` model.
 *
 * The fourth pass made the side card (analysis/findings) the flex:1 primary
 * region unconditionally, so the document was always a fixed ~380px companion
 * panel whether shown or not. The owner reviewed that against the earlier
 * (third-pass) behaviour — the document going WIDE when explicitly opened,
 * the side card becoming the narrow rail beside it — and asked for that back:
 * "when I click show doc [...] the screen that used to appear, that was
 * fine". So: CLOSED, the side card still fills the whole workspace exactly as
 * the fourth pass left it (that half was never the complaint). OPEN, the
 * document is once again the wide `1fr` column and the side card is the fixed
 * `var(--ws-side-w)` rail — the opposite of the fourth pass's open state, and
 * a return to the third pass's.
 *
 * `docOpen` — one boolean, not two named states — is kept from the fourth
 * pass; only which grid column each region draws when it is `true` changes,
 * driven here by DOM order (document first again) rather than a second state
 * to track. Pointing at evidence still opens the panel by itself (see the
 * effect below) — a citation click has to end with the passage visible.
 */
const DOC_OPEN_KEY = "legalmind.workspace.docOpen";

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
// page 2: "Points" — the word the Summary, the counts and the cards all use
const LABEL: Record<Region, string> = {
  document: "Document",
  findings: "Points",
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
  /** The reader's three-word status (AM-50 r4) — what the Summary tiles point with. */
  status?: "ACCEPTABLE" | "NEEDS_DECISION" | "REQUIRES_MODIFICATION" | "MISSING";
  /** The workflow field `finding.requires_decision` — what the Summary's
      "Review pending decisions" counts, and so what it must point with. It is
      not a reader status: a finding can require a decision and still read
      "Requires modification". */
  requiresDecision?: true;
  /** Every point not Acceptable — the Summary's "open" count (owner, 2026-10-21). */
  open?: true;
  /** Where the points stand (AM-179) — what the Summary's stage line points with. */
  state?: "to_decide" | "clarification" | "decided" | "matches";
  /** The points decided this way — what the Summary's "What was decided" points with. */
  decision?: string;
  findingId?: string;
  seq: number;
}

/** Lets the Analysis panel open the Findings tab, optionally pointed.
 *  Exported for the static test suite; the workspace reads it through `useSideTabs`. */
export const SideTabCtx = createContext<{
  openFindings: (target?: Omit<FindingsPoint, "seq">) => void;
  findingsPoint: FindingsPoint | null;
  /** Bumped whenever a side tab is chosen: Ask, which takes the whole column
   *  while open (2026-09-10), closes so the chosen tab is actually visible. */
  closeAskSeq: number;
  /** On a wide screen Ask is the third tab of the Summary/Findings row at every width
   *  (owner, 2026-11-02: one Ask surface, the document keeps the room — the 1680px
   *  Ask column of 2026-10-08 is withdrawn), so its open state lives here. */
  askOpen?: boolean;
  setAskOpen?: React.Dispatch<React.SetStateAction<boolean>>;
  /** Bumped when the reader opens Ask from that row: the one time its input takes
   *  focus, so a column shown on load never steals it. */
  askFocusSeq?: number;
  /** Hides the document from its own header (owner, 2026-10-08). */
  hideDocument?: () => void;
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
function storedDocOpen(): boolean {
  try {
    // Absent means OPEN. The document is the primary reference surface
    // (owner, 2026-09-09), so a reader who has never touched the toggle
    // gets it; only an explicit "Hide document" is remembered.
    return window.localStorage.getItem(DOC_OPEN_KEY) !== "0";
  } catch {
    return true;
  }
}

/** WAI-ARIA tabs: Left/Right move the selection and the focus round the tablist, so the
 *  list is one tab stop. `pick` selects the tab at that index. */
export function arrowTab(event: React.KeyboardEvent<HTMLElement>, index: number, count: number,
                         pick: (next: number) => void) {
  if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
  const next = (index + (event.key === "ArrowRight" ? 1 : -1) + count) % count;
  pick(next);
  event.currentTarget.parentElement?.querySelectorAll<HTMLElement>('[role="tab"]')[next]?.focus();
  event.preventDefault();
}

/** `null` until measured: the server has no viewport, so the first client render
 *  cannot know it either without a hydration mismatch. */
export function useMinWidth(px: number): boolean | null {
  const [matches, setMatches] = useState<boolean | null>(null);
  useEffect(() => {
    const query = window.matchMedia(`(min-width: ${px}px)`);
    const apply = () => setMatches(query.matches);
    apply();
    query.addEventListener("change", apply);
    return () => query.removeEventListener("change", apply);
  }, [px]);
  return matches;
}

function useMode(): Mode {
  return useMinWidth(900) === false ? "one" : "wide";
}

/** Heard, not shown: "Ask about this document", the name the launcher always had. */
const ASK_NAME_TAIL = <span className="ws-visually-hidden"> about this document</span>;

/** A deep link into a finding or a classification filter must land on the
 *  findings view, not behind the analysis tab. */
function initialSideTab(): SideTab {
  if (typeof window === "undefined") return "analysis";
  const params = new URLSearchParams(window.location.search);
  return params.get("finding") || params.get("classification") ? "findings" : "analysis";
}

/** The phone's one tab row (polish batch, 2026-11-03): the record page owns the region and
 *  Ask's open state, so Contract · Summary · Points · Changes · Ask are one bar there. */
export interface PhoneTabs {
  tab: Region;
  setTab: (region: Region) => void;
  askOpen: boolean;
  setAskOpen: React.Dispatch<React.SetStateAction<boolean>>;
  askFocusSeq: number;
}

export function WorkspaceLayout({
  document,
  findings,
  analysis,
  ask,
  phone,
}: Record<Region, React.ReactNode> & {
  /** Given, the narrow layout draws no tab row of its own: the page's bar is the one row. */
  phone?: PhoneTabs | undefined;
  /* Ask, DOCKED into the right column rather than floating over the canvas
     (owner, 2026-09-09, superseding DD-15). As a flow child of the column it
     reserves space only while it is open, so it can never come to rest over the
     document or a finding — WCAG 2.2 AA 2.4.11 names chat widgets as the
     failure case, and the floating panel was one. Closed, it is the compact
     launcher at the foot of the column, which is what reopens it. */
  ask?: React.ReactNode;
}) {
  const mode = useMode();
  /* Placed once the width is known: the narrow layout mounts it elsewhere, and a
     first render in the wrong place would remount it — two history requests. */
  const askPlaced = useMinWidth(900) === null ? null : ask;
  /* Above the narrow-mode early return below: a hook after a conditional return
     runs on some renders and not others, which is React error #310 — and it
     showed up as the collapsed layout rendering no tabs at all. */
  const shortcuts = useWorkspaceShortcuts();
  const [ownTab, setOwnTab] = useState<Region>("document");
  const phoneTabs = mode === "one" ? phone : undefined;
  const tab = phoneTabs?.tab ?? ownTab;
  const setTab = phoneTabs?.setTab ?? setOwnTab;
  /* Read in the initialiser, so the first paint already has the final columns: reading
     it after mount drew the side card full-width and then shrank it (CLS 0.4–0.5).
     Safe here because this layout only mounts once the contract has loaded in the
     browser — the server never renders it, so there is nothing to mismatch. */
  const [docOpen, setDocOpen] = useState(storedDocOpen);
  const chooseDocOpen = useCallback((next: boolean) => {
    setDocOpen(next);
    try {
      window.localStorage.setItem(DOC_OPEN_KEY, next ? "1" : "0");
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
    if (target) setDocOpen(true);
  }, [target]);
  const [sideTab, setSideTab] = useState<SideTab>(initialSideTab);
  const [findingsPoint, setFindingsPoint] = useState<FindingsPoint | null>(null);

  const [closeAskSeq, setCloseAskSeq] = useState(0);
  // Ask is a tab: it covers Summary/Findings while open, so it starts closed.
  const [askTabOpen, setAskOpen] = useState(false);
  const [askFocusSeq, setAskFocusSeq] = useState(0);
  const askInTabs = mode === "wide" && ask !== undefined;
  /** Opened by a click: the input takes focus. By arrow keys: focus stays on the
   *  tab, so the reader can keep moving along the row. */
  const openAsk = (focusInput = true) => {
    setAskOpen(true);
    if (focusInput) setAskFocusSeq((n) => n + 1);
  };
  const chooseSideTab = useCallback((which: SideTab) => {
    setSideTab(which);
    setAskOpen(false);
    setCloseAskSeq((n) => n + 1);
  }, []);
  const openFindings = useCallback((target?: Omit<FindingsPoint, "seq">) => {
    chooseSideTab("findings");
    setTab("findings");
    if (target) setFindingsPoint((p) => ({ ...target, seq: (p?.seq ?? 0) + 1 }));
  }, [chooseSideTab, setTab]);
  // the header's "Decide N points" (`nextStep`): the open points, on the Points tab
  useStep("decide", useCallback(() => openFindings({ state: "to_decide" }), [openFindings]));
  const sideCtx = useMemo(
    () => ({ openFindings, findingsPoint, closeAskSeq,
             ...(askInTabs ? { askOpen: askTabOpen, setAskOpen, askFocusSeq } : {}),
             ...(phoneTabs ? { askOpen: phoneTabs.askOpen, setAskOpen: phoneTabs.setAskOpen,
                               askFocusSeq: phoneTabs.askFocusSeq } : {}),
             ...(mode === "wide" ? { hideDocument: () => {
               chooseDocOpen(false);
               // The control pressed is gone with the document; its twin brings it back.
               requestAnimationFrame(() =>
                 window.document.querySelector<HTMLElement>(".ws-side__doctoggle")?.focus());
             } } : {}) }),
    [openFindings, findingsPoint, closeAskSeq, askInTabs, askTabOpen, askFocusSeq, mode,
     chooseDocOpen, phoneTabs],
  );

  // ---- narrow: one region at a time, top tabs -----------------------------
  const tabbed: Region[] = ["document", "analysis", "findings"];

  if (mode === "one") {
    return (
      <SideTabCtx.Provider value={sideCtx}>
        {/* The sheet is mounted in BOTH layouts: a keyboard user on a narrow
            screen needs it at least as much as one on a wide screen. */}
        <KeyboardShortcutsHelp open={shortcuts.helpOpen} onClose={shortcuts.closeHelp} />
        {phoneTabs ? null : <div className="ws-tabs" role="tablist" aria-label="Workspace regions">
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
              onKeyDown={(event) => arrowTab(event, index, tabbed.length, (i) => setTab(tabbed[i]!))}
            >
              {/* "Contract" here: the record's own tab row above already says "Document". */}
              {region === "document" ? "Contract" : LABEL[region]}
            </button>
          ))}
        </div>}
        <div className="ws-workspace ws-workspace--one" data-mode="one" data-phone={phoneTabs ? "" : undefined}>
          <section
            className="ws-pane"
            id={`ws-pane-${tab}`}
            role="tabpanel"
            aria-labelledby={`ws-tab-${tab}`}
            data-region={tab}
          >
            {{ document, findings, analysis }[tab]}
          </section>
          {/* One region at a time, so Ask cannot take a column here: it stays
              the launcher plus an overlay sheet (its own narrow-mode CSS), the
              behaviour DD-15 shipped and the only one a single-column layout
              can offer. */}
          {ask}
        </div>
      </SideTabCtx.Provider>
    );
  }

  // ---- wide: document area + the side card with internal tabs -------------
  /* Ask is the third tab while it shares the column (owner, 2026-10-08: the Ask
     launcher at the foot of the column moves up beside Summary and Findings). It
     already behaved as one — open, it takes the column; choosing Summary or
     Findings closes it — so the strip now says so. */
  const sideTabs: (SideTab | "ask")[] = askInTabs ? ["analysis", "findings", "ask"] : ["analysis", "findings"];
  const chooseTab = (which: SideTab | "ask", byKey = false) =>
    which === "ask" ? openAsk(!byKey) : chooseSideTab(which);
  const selected = (which: SideTab | "ask") =>
    which === "ask" ? askTabOpen : !(askInTabs && askTabOpen) && sideTab === which;

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
      {/* The DOCUMENT first (owner, 2026-09-09, amending AM-50 r5): it is the
          primary reference surface of a legal review, so it draws the flexible
          centre column and carries its own contents index on its left. The
          side card — findings, analysis and Ask — is the fixed right column.
          When the document is hidden the side card fills the workspace, exactly
          as before. DOM order drives visual and tab order together. */}
      <div className="ws-workspace ws-workspace--wide" data-mode="wide" data-doc-open={docOpen}>
        <section
          className="ws-pane ws-pane--document"
          id="ws-pane-document"
          aria-label="Document"
          data-region="document"
          /* `inert`, not unmounted: the pane keeps its scroll position, its
             Original/Text choice and its outline state, so revealing it returns
             the reader to where they were. `hidden` would take it out of the
             accessibility tree AND stop the scroll-to-evidence gesture from
             finding its rows, so the CSS hides it and `inert` keeps it out of
             the tab order while it is not shown. */
          inert={docOpen ? undefined : true}
        >
          {document}
        </section>
        <section className="ws-pane ws-pane--side" aria-label="Analysis and findings">
          <div className="ws-side__tabs">
            <div className="ws-side__tablist" role="tablist" aria-label="Analysis views">
            {sideTabs.map((which, index) => (
              <button
                key={which}
                type="button"
                role="tab"
                id={`ws-tab-${which}`}
                aria-selected={selected(which)}
                aria-controls={`ws-pane-${which}`}
                tabIndex={selected(which) ? 0 : -1}
                onClick={() => chooseTab(which)}
                onKeyDown={(event) => arrowTab(event, index, sideTabs.length, (i) => chooseTab(sideTabs[i]!, true))}
              >
                {which === "ask" ? <><IconSparkle size={15} /> Ask{ASK_NAME_TAIL}</> : LABEL[which]}
              </button>
            ))}
            </div>
            {/* The document, on request. A real toggle rather than a tab: the
                document is not a view OF the analysis, it is the thing the analysis
                is about, and in the open state both are on screen at once — which no
                tab set can express. The Contents panel's own collapse icon (owner,
                2026-10-08), so one gesture means one thing in both places; the
                words stay as its accessible name and tooltip. */}
            <button
              type="button"
              className="ws-outline__collapse ws-side__doctoggle"
              aria-pressed={docOpen}
              aria-controls="ws-pane-document"
              aria-label={docOpen ? "Hide document" : "Show document"}
              title={docOpen ? "Hide document" : "Show document"}
              onClick={() => chooseDocOpen(!docOpen)}
            >
              {docOpen
                ? <PanelLeftClose size={16} aria-hidden focusable="false" />
                : <PanelLeftOpen size={16} aria-hidden focusable="false" />}
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
          {askPlaced}
        </section>
      </div>
    </SideTabCtx.Provider>
  );
}

export type PhoneView = Region | "changes";

/**
 * The phone's ONE tab row (polish batch, 2026-11-03), a bottom bar as in Material's and
 * iOS's navigation bars: the four views as tabs, Ask as the fifth button that opens its
 * sheet. It replaces three stacked rows (Document/Changes, Contract/Summary/Points and the
 * version select) that came before any content.
 */
export function PhoneBar({ view, onView, changesBadge, askOpen, onAsk }: {
  view: PhoneView;
  onView: (view: PhoneView) => void;
  /** Absent: the contract has no client changes, so there is no Changes tab. */
  changesBadge?: number | null | undefined;
  askOpen: boolean;
  /** Absent: Ask is not offered here. */
  onAsk?: (() => void) | undefined;
}) {
  const views: PhoneView[] = ["document", "analysis", "findings",
    ...(changesBadge !== undefined ? ["changes" as const] : [])];
  const ICON: Record<PhoneView, React.ReactNode> = {
    document: <FileText size={20} aria-hidden focusable="false" />,
    analysis: <LayoutList size={20} aria-hidden focusable="false" />,
    findings: <ListChecks size={20} aria-hidden focusable="false" />,
    changes: <GitCompareArrows size={20} aria-hidden focusable="false" />,
  };
  const name = (v: PhoneView) => (v === "document" ? "Contract" : v === "changes" ? "Changes" : LABEL[v]);
  return (
    <nav className="ws-phonebar" aria-label="Contract views">
      <div className="ws-phonebar__tabs" role="tablist" aria-label="Contract views">
        {views.map((v, index) => {
          const on = !askOpen && view === v;
          return (
            <button key={v} type="button" role="tab" id={`ws-tab-${v}`} aria-selected={on}
                    aria-controls={v === "changes" ? undefined : `ws-pane-${v}`}
                    tabIndex={on || (askOpen && index === 0) ? 0 : -1}
                    onClick={() => onView(v)} onKeyDown={(event) => arrowTab(event, index, views.length, (i) => onView(views[i]!))}>
              <span className="ws-phonebar__icon">
                {ICON[v]}
                {v === "changes" && changesBadge
                  ? <span className="ws-phonebar__badge" aria-hidden="true">{changesBadge}</span> : null}
              </span>
              <span className="ws-phonebar__label">{name(v)}</span>
              {v === "changes" && changesBadge
                ? <span className="ws-visually-hidden">, {changesBadge} yours</span> : null}
            </button>
          );
        })}
      </div>
      {onAsk ? (
        <button type="button" id="ws-tab-ask" className="ws-phonebar__ask" aria-expanded={askOpen}
                aria-controls="ws-pane-ask" onClick={onAsk}>
          <span className="ws-phonebar__icon"><IconSparkle size={20} /></span>
          <span className="ws-phonebar__label">Ask</span>
          <span className="ws-visually-hidden"> about this document</span>
        </button>
      ) : null}
    </nav>
  );
}
