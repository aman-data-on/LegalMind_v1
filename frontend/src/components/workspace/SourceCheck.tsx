"use client";

/** Source integrity B1: every Copy meant for a client asks the server first
 *  (`POST /outgoing/check`). The server names each problem and says whether it blocks;
 *  this file only shows that and copies when the server says it may. A clipboard check
 *  is a guard, not a control, and the help text says so. */
import { createContext, useContext, useId, useState, type ReactNode } from "react";

import { api, type OutgoingCheck, type OutgoingSurface } from "@/lib/api";
import { SOURCE_CHECK } from "@/lib/labels";

/** The Ask chat on screen, so Copy email can send the answer's cited keys with it. */
export const AskConversation = createContext<string | null>(null);

type State =
  | { kind: "idle" }
  | { kind: "busy" }
  | { kind: "done"; result: OutgoingCheck; copied: boolean }
  | { kind: "failed" };

/** A Copy button's check. ``copy(text)`` resolves true when the text was copied. */
export function useCheckedCopy(surface: OutgoingSurface, keys: string[] = []) {
  const conversationId = useContext(AskConversation);
  const [state, setState] = useState<State>({ kind: "idle" });
  const [text, setText] = useState("");

  async function run(body: string, overrideReason?: string): Promise<boolean> {
    setText(body);
    setState({ kind: "busy" });
    let result: OutgoingCheck;
    try {
      result = await api.checkOutgoing({
        surface, text: body,
        ...(conversationId && keys.length ? { conversation_id: conversationId, keys } : {}),
        ...(overrideReason ? { override_reason: overrideReason } : {}),
      });
    } catch {
      setState({ kind: "failed" });
      return false;
    }
    let copied = false;
    if (!result.blocked) {
      copied = await navigator.clipboard?.writeText(body).then(() => true, () => false) ?? false;
    }
    setState({ kind: "done", result, copied });
    return copied;
  }

  const panel = state.kind === "failed" ? <p className="ws-srccheck__error" role="alert">{SOURCE_CHECK.failed}</p>
    : state.kind === "done" && state.result.problems.length
      ? <SourceProblems result={state.result} onOverride={(reason) => void run(text, reason)} />
      : null;
  return { copy: (body: string) => run(body), busy: state.kind === "busy",
           copied: state.kind === "done" && state.copied, panel };
}

export function SourceProblems({ result, onOverride, checkOnly = false }: {
  result: OutgoingCheck;
  onOverride?: ((reason: string) => void) | undefined;
  /** the paste-to-check box copies nothing, so it never says "Not copied" */
  checkOnly?: boolean;
}) {
  const [reason, setReason] = useState("");
  const [missing, setMissing] = useState(false);
  const id = useId();
  const blocked = result.blocked;
  return (
    <section className="ws-srccheck" role={blocked ? "alert" : "status"}
             aria-label={checkOnly ? SOURCE_CHECK.pasteFound : blocked ? SOURCE_CHECK.blockedTitle : SOURCE_CHECK.warnTitle}>
      <p className="ws-srccheck__title">
        {result.overridden ? SOURCE_CHECK.overridden
          : checkOnly ? SOURCE_CHECK.pasteFound
            : blocked ? SOURCE_CHECK.blockedTitle : SOURCE_CHECK.warnTitle}
      </p>
      <ul className="ws-srccheck__list">
        {result.problems.map((p, i) => (
          <li key={i} data-blocks={p.blocks || undefined}>
            {p.message}
            {p.current_wording && !p.message.includes(p.current_wording) ? (
              <><span className="ws-srccheck__says"> {SOURCE_CHECK.currentSays}</span>
                <q className="ws-srccheck__quote">{p.current_wording}</q></>
            ) : null}
          </li>
        ))}
      </ul>
      {blocked && !result.can_override ? <p className="ws-srccheck__help">{SOURCE_CHECK.askLegal}</p> : null}
      {blocked && result.can_override && onOverride ? (
        <form className="ws-srccheck__override" onSubmit={(e) => {
          e.preventDefault();
          if (!reason.trim()) { setMissing(true); return; }
          onOverride(reason.trim());
        }}>
          <label htmlFor={`${id}-reason`}>{SOURCE_CHECK.overrideLabel}</label>
          <textarea id={`${id}-reason`} rows={2} value={reason}
                    aria-describedby={missing ? `${id}-missing` : undefined}
                    onChange={(e) => { setReason(e.target.value); setMissing(false); }} />
          {missing ? <p id={`${id}-missing`} className="ws-srccheck__error">{SOURCE_CHECK.overrideNeedsReason}</p> : null}
          <button type="submit" className="ws-btn ws-btn--sm">{SOURCE_CHECK.overrideButton}</button>
        </form>
      ) : null}
      {checkOnly ? null : <p className="ws-srccheck__help">{SOURCE_CHECK.guardNote}</p>}
    </section>
  );
}

/** Ask's paste-to-check box (S7): the only check that reaches text drafted outside
 *  LegalMind. Nothing is recorded; nothing is copied. */
export function PasteCheck(): ReactNode {
  const [draft, setDraft] = useState("");
  const [state, setState] = useState<State>({ kind: "idle" });
  const id = useId();
  return (
    <details className="ws-srccheck__paste">
      <summary>{SOURCE_CHECK.pasteTitle}</summary>
      <p className="ws-srccheck__help">{SOURCE_CHECK.pasteHelp}</p>
      <form onSubmit={(e) => {
        e.preventDefault();
        if (!draft.trim()) return;
        setState({ kind: "busy" });
        api.checkOutgoing({ surface: "paste_check", text: draft }).then(
          (result) => setState({ kind: "done", result, copied: false }),
          () => setState({ kind: "failed" }));
      }}>
        <label htmlFor={`${id}-draft`}>{SOURCE_CHECK.pasteLabel}</label>
        <textarea id={`${id}-draft`} rows={5} value={draft} onChange={(e) => setDraft(e.target.value)} />
        <button type="submit" className="ws-btn ws-btn--sm" disabled={state.kind === "busy"}
                aria-busy={state.kind === "busy" || undefined}>
          {state.kind === "busy" ? SOURCE_CHECK.checking : SOURCE_CHECK.pasteButton}
        </button>
      </form>
      <div aria-live="polite">
        {state.kind === "failed" ? <p className="ws-srccheck__error" role="alert">{SOURCE_CHECK.failed}</p> : null}
        {state.kind === "done" && state.result.problems.length === 0
          ? <p className="ws-srccheck__ok">{SOURCE_CHECK.pasteClear}</p> : null}
        {state.kind === "done" && state.result.problems.length
          ? <SourceProblems result={state.result} checkOnly /> : null}
      </div>
    </details>
  );
}
