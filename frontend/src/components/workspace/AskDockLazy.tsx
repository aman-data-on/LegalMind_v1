"use client";

/**
 * Ask, loaded when it is first wanted (UI review item 6, 2026-11-06). The dock carries
 * assistant-ui, its runtime and the answer renderers — most of the contract page's
 * script — and it used to load and fetch its chat history on every contract page,
 * open or not. This light wrapper mounts the real dock the first time Ask opens (its
 * tab, the phone's Ask button, or a finding's "Ask about this" draft), then keeps it
 * mounted so the conversation survives closing.
 */
import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

import { useAskIntent } from "./askIntent";
import { useSideTabs } from "./WorkspaceLayout";

type DockProps = React.ComponentProps<typeof import("./AskDock").AskDock>;

/** While the script arrives: the open panel's frame, at its final place. Escape closes
 *  it, as it closes the dock. */
function Opening() {
  const setAskOpen = useSideTabs()?.setAskOpen;
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") setAskOpen?.(false); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [setAskOpen]);
  return (
    <div className="ws-dock" data-open="true" data-in-tabs="true">
      <section className="ws-dock__panel" id="ws-pane-ask" aria-busy="true" aria-label="Ask about this document">
        <p className="ws-pane__note" role="status">Opening Ask…</p>
      </section>
    </div>
  );
}

const AskDock = dynamic(() => import("./AskDock").then((m) => m.AskDock), { ssr: false, loading: Opening });

export function AskDockLazy(props: DockProps) {
  const side = useSideTabs();
  const draft = useAskIntent()?.draft ?? null;
  /* The draft present when this wrapper mounted was handed to an earlier dock (the
     layout moving it between arrangements); the dock must not replay it, but a draft
     that ARRIVES later — the one that opens Ask — it applies. */
  const [seenDraft] = useState(draft?.seq ?? 0);
  const [seenFocus] = useState(side?.askFocusSeq ?? 0);
  const wantedNow = Boolean(side?.askOpen) || (draft !== null && draft.seq !== seenDraft);
  // once wanted, always mounted (state adjusted while rendering, React's own pattern)
  const [wanted, setWanted] = useState(wantedNow);
  if (wantedNow && !wanted) setWanted(true);
  return wanted || wantedNow ? <AskDock {...props} skipDraftSeq={seenDraft} skipFocusSeq={seenFocus} /> : null;
}
