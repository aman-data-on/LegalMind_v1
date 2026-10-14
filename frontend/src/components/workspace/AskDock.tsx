"use client";

/**
 * Ask about this document — a SECONDARY, floating interaction (owner directive,
 * 2026-09-02; DD-15, superseding DD-9 §4).
 *
 * What changed and why
 * --------------------
 * The former `AskBar` was a permanent row at the bottom of `.ws-workmain`: an
 * input, a suggestion-chip row and an honesty note, ~128px of the workspace's
 * height reserved on every screen whether or not anyone was asking anything.
 * The owner's objection is a hierarchy objection, not a styling one — the
 * document, the clauses and the findings are the work; Ask is a tool you reach
 * for. So Ask now occupies NO layout row at all. It is a launcher pinned in the
 * bottom-right of the workspace, and the conversation opens over the canvas.
 *
 * The interaction pattern, and why not hover
 * ------------------------------------------
 * A disclosure, not a modal, and click/Enter/Space — never hover-to-open. Hover
 * cannot be performed on a touch screen at all, and a corner panel that opens on
 * pointer transit opens constantly by accident while someone is reading. Hover
 * therefore drives visual affordance only. The panel is `role="dialog"` with
 * `aria-modal="false"`: focus is MOVED to the input on open but never trapped,
 * so a reader can tab straight back out into the clause list, click a clause, or
 * scroll the document with the conversation still open. Escape closes and
 * returns focus to the launcher.
 *
 * The launcher floats above the panels, so — WCAG 2.2 AA 2.4.11, "Focus Not
 * Obscured", which names chat widgets explicitly — the scrolling panels carry
 * bottom padding equal to its footprint (`workspace.css`), and it hides itself
 * while the conversation is open. Nothing can come to rest underneath it.
 *
 * Version context is now explicit, and that is the actual defect fixed
 * ---------------------------------------------------------------------
 * Ask used to be DISABLED whenever an older version was open, with a button
 * offering to "open the latest version" — because the server always answered
 * from the newest version, so an answer's citations pointed at evidence rows
 * that are not in the open version's reading order. The API now takes the
 * version being asked about, so Ask works on EVERY version: it answers about the
 * document on screen and names which one in its header.
 *
 * A conversation is contract-scoped (`AM-27`: "an assist-lane session"), so a
 * transcript may legitimately contain turns answered from different versions.
 * Each answer therefore carries its own version, a turn from another version
 * says so, and its citations offer to open THAT version rather than pretending
 * to highlight a row the open page does not contain.
 *
 * Unchanged from the former bar, deliberately:
 *
 *   ANSWERED            prose + numbered citations; each citation POINTS at its
 *                       evidence row through the slice-1 highlight gesture
 *   a refusal           the identical sentence whatever the cause (`AM-29` r4),
 *                       on the quiet surface — the system working, not failing
 *   routed_to_evaluator a compliance-shaped question is a pointer to the
 *                       Findings pane, a third type, not an answer or a refusal
 *
 * The conversation is durable: on mount the dock reopens this contract's most
 * recent conversation — the server keeps citations across reloads. A finding's
 * "Ask about this" arrives as an EDITABLE draft (askIntent), which OPENS the
 * dock and focuses the input, and never sends. One honest status line while a
 * request is in flight (decision #180); scores are retrieval scores, labelled as
 * exactly that (`AI-03` item 16, rule 12).
 */

import { AssistantRuntimeProvider } from "@assistant-ui/react";
import Link from "next/link";
import { useCallback, useEffect, useId, useRef, useState } from "react";
import { sectionRef } from "@/lib/documentTypes";
import { classificationLabel } from "@/lib/labels";

import { ASK_TIMEOUT_MS, ApiError, api, describeError } from "@/lib/api";
import { Thread } from "@/components/ui/thread";
import type {
  AskResult, AssistComparison, AssistPosition, AssistStatuteAnswer, ConversationSummary,
  ConversationTurn,
} from "@/lib/types";

import { useAskIntent } from "./askIntent";
import { USER_STATUS_LABELS } from "./findingLanguage";
import { AnswerMeta, AnswerProse, citesPositions, type ShowInDocument, sourceKind } from "./AnswerProse";
import { useHighlight } from "./highlight";
import { IconPlus, IconSparkle, IconX } from "./icons";
import { useSideTabs } from "./WorkspaceLayout";
import {
  STOPPED, type Pending, answerOf, arrived, before, chatTitle, enterSends, isImeEnter, liveTurns,
  useAskRuntime, useFocusAfterAnswer, waitEnded,
} from "./askThread";

export function AskDock({
  contractId,
  documentVersionId,
  versionNumber,
  isLatest,
  onOpenVersion,
}: {
  /** Null on the Research surface: a document-less conversation answered from the
   *  approved statute corpus and positions (2026-09-08). */
  contractId: string | null;
  /** The version on screen — what a question is about. */
  documentVersionId: string | null;
  versionNumber: number | null;
  /** Whether the open version is the newest; used for the header's wording only. */
  isLatest: boolean;
  /** Open another version — for a citation belonging to a different one. */
  onOpenVersion?: ((documentVersionId: string) => void) | undefined;
}) {
  const askIntent = useAskIntent();
  const [turns, setTurns] = useState<ConversationTurn[]>([]);
  /** This document's chats (`AM-135`): all of them are found here, not only the latest. */
  const [chats, setChats] = useState<ConversationSummary[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [restoring, setRestoring] = useState(true);
  const [pending, setPending] = useState<Pending | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [announce, setAnnounce] = useState("");
  const [failed, setFailed] = useState<{ text: string; editOf?: string | undefined } | null>(null);
  const sideTabs = useSideTabs();
  const [localOpen, setLocalOpen] = useState(false);
  /* On a wide screen the workspace holds whether Ask is open (owner, 2026-10-08):
     the "Ask" control in the Summary/Findings row opens it — as the third tab where
     it shares that column, as its own column from 1680px — so the launcher at the
     foot of the column is gone and the close button folds it back into that row. */
  const controlled = Boolean(sideTabs?.setAskOpen);
  const open = controlled ? Boolean(sideTabs?.askOpen) : localOpen;
  const setOpen = controlled ? sideTabs!.setAskOpen! : setLocalOpen;
  const railed = sideTabs?.askRail ?? false;
  /** The chat on screen, read after an await: an answer belongs to the chat it was asked
   *  in. Switching chats waits while an answer is found, so this only ever moves between
   *  questions. */
  const conversationRef = useRef<string | null>(null);
  conversationRef.current = conversationId;
  const abortRef = useRef<AbortController | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const launcherRef = useRef<HTMLButtonElement>(null);
  const logRef = useRef<HTMLDivElement>(null);
  const busy = pending !== null;
  const titleId = useId();
  const chatsId = useId();
  // The Ask tab controls this panel by a fixed id; the launcher by its own.
  const panelId = controlled ? "ws-pane-ask" : `${titleId}-panel`;

  const loadChats = useCallback(async () => {
    if (!contractId) return [];
    const { items } = await api.conversations({ contract_id: contractId, page_size: 20 });
    setChats(items);
    return items;
  }, [contractId]);

  /** The latest chat asked for wins: a slower earlier read never lands over it. */
  const openSeq = useRef(0);
  /** The chat being opened. A question sent meanwhile waits for it, then goes into that
   *  chat — never dropped, and never into a new chat the opened one then covers. */
  const opening = useRef<Promise<void>>(Promise.resolve());
  const openChat = useCallback((id: string | null) => {
    const seq = ++openSeq.current;
    setConversationId(id);
    setError(null);
    setFailed(null);
    setTurns([]);
    if (!id) return (opening.current = Promise.resolve());
    setRestoring(true);
    return (opening.current = (async () => {
      try {
        const { messages } = await api.conversation(id);
        if (seq === openSeq.current) setTurns(messages);
      } catch (cause) {
        if (seq === openSeq.current) setError(describeError(cause));
      } finally {
        if (seq === openSeq.current) setRestoring(false);
      }
    })());
  }, []);

  // This document's chats, the most recent open, citations intact. Scoped to the
  // contract, not the version: the history belongs to the document, and each turn
  // reports which version answered it.
  useEffect(() => {
    let cancelled = false;
    opening.current = (async () => {
      try {
        const items = await loadChats();
        if (!cancelled && items[0]) await openChat(items[0].id);
      } catch {
        // History is a convenience; asking still works without it.
      } finally {
        if (!cancelled) setRestoring(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [loadChats, openChat]);

  /** Every send — the composer's, an edit (`AM-134`) and "Try again". */
  async function submit(typed: string, editOf?: string) {
    const asked = typed.trim();
    if (!asked || busy) return;
    const composer = runtime.thread.composer;
    if (composer.getState().text.trim() === asked) composer.setText("");
    setPending({ text: asked, editOf });
    setAnnounce("");
    setError(null);
    setFailed(null);
    await opening.current;
    const askedIn = conversationRef.current;
    const abort = new AbortController();
    abortRef.current = abort;
    const timer = window.setTimeout(() => abort.abort(), ASK_TIMEOUT_MS);
    try {
      let conversation = askedIn;
      if (!conversation) {
        conversation = (await api.createConversation(contractId)).id;
        setConversationId(conversation);
      }
      // The version on screen is the version asked about — never "whichever is
      // newest" — and a Finding's draft seeds this send only.
      const findingId = draftFinding.current ?? undefined;
      draftFinding.current = null;
      const result = await api.ask(conversation, asked, documentVersionId ?? undefined,
                                   findingId, abort.signal, undefined, editOf);
      setTurns((previous) => [...before(previous, editOf), ...liveTurns(asked, result)]);
      setAnnounce(arrived(result));
    } catch (cause) {
      const gone = cause instanceof ApiError && cause.isNotFound;
      setFailed({ text: asked, editOf: gone ? undefined : editOf });
      // An edit's text stays an edit ("Try again"); a question's comes back to the box.
      if (!editOf && !composer.getState().text.trim()) composer.setText(asked);
      if (editOf && askedIn && !abort.signal.aborted) {
        // Only into the chat it came from: another opened meanwhile keeps its own turns.
        api.conversation(askedIn).then((detail) => {
          if (conversationRef.current === askedIn) setTurns(detail.messages);
        }, () => undefined);
      }
      setError(abort.signal.aborted ? waitEnded(abort.signal.reason) : describeError(cause));
    } finally {
      window.clearTimeout(timer);
      abortRef.current = null;
      setPending(null);
      // A chat this send created is listed even when its first answer failed.
      if (!askedIn && conversationRef.current) void loadChats();
    }
  }

  const runtime = useAskRuntime({
    turns, pending, busy, send: submit,
    stop: () => abortRef.current?.abort(STOPPED),
  });
  useFocusAfterAnswer(busy, inputRef);

  // A finding's handoff: open the dock, place the draft, focus the input, send
  // nothing. Opening is part of the handoff now that the input is not always on
  // screen — otherwise "Ask about this" would silently do nothing visible.
  /* Starts at the draft already handed over, so a dock mounted afresh (the layout
     moving it between arrangements) never replays a draft it already applied. */
  const consumedSeq = useRef(askIntent?.draft?.seq ?? 0);
  /** The Finding the pending draft came from, if any — a retrieval hint for the
   *  NEXT send only, cleared the moment it is used so a later, unrelated question
   *  in the same conversation is not quietly seeded with a stale clause. */
  const draftFinding = useRef<string | null>(null);
  useEffect(() => {
    const draft = askIntent?.draft;
    if (!draft || draft.seq === consumedSeq.current) return;
    consumedSeq.current = draft.seq;
    runtime.thread.composer.setText(draft.text);
    draftFinding.current = draft.findingId ?? null;
    setOpen(true);
    if (controlled) requestAnimationFrame(() => inputRef.current?.focus());
  }, [askIntent?.draft]);

  /* Focus follows disclosure, in both directions: the input on open, the launcher
   * on close. Never a trap — the panel is not modal, so a reader can tab straight
   * out into the clause list with the conversation still open.
   *
   * It has to run in an effect rather than in the click handler: the launcher is
   * `hidden` while the panel is open, and focusing a hidden element does nothing.
   * Restoring focus therefore has to wait until React has re-rendered it visible.
   * `wasOpen` keeps this from stealing focus on first mount, when nothing was
   * closed and the reader may be anywhere on the page. */
  const wasOpen = useRef(false);
  useEffect(() => {
    if (controlled) return;   // the workspace's own control moves focus (below)
    if (open) inputRef.current?.focus();
    else if (wasOpen.current) launcherRef.current?.focus();
    wasOpen.current = open;
  }, [open, controlled]);
  /* Controlled, Ask can also open without a gesture — a wide screen shows its column
     on load — so the input takes focus only when the reader asked for it, which the
     workspace counts in `askFocusSeq`; closing returns focus to the "Ask" control. */
  const askFocusSeq = sideTabs?.askFocusSeq ?? 0;
  const seenFocusSeq = useRef(askFocusSeq);
  useEffect(() => {
    if (askFocusSeq === seenFocusSeq.current) return;
    seenFocusSeq.current = askFocusSeq;
    requestAnimationFrame(() => inputRef.current?.focus());
  }, [askFocusSeq]);

  const close = useCallback(() => {
    setOpen(false);
    if (controlled) requestAnimationFrame(() => document.getElementById("ws-tab-ask")?.focus());
  }, [setOpen, controlled]);

  /* Open, Ask takes the whole side column (owner, 2026-09-10: "a proper
   * conversational AI workspace… dock Ask as a right-side panel"), so choosing
   * Summary or Findings has to close it or the chosen tab would stay hidden. */
  const closeAskSeq = useSideTabs()?.closeAskSeq ?? 0;
  const seenCloseSeq = useRef(closeAskSeq);
  useEffect(() => {
    if (closeAskSeq === seenCloseSeq.current) return;
    seenCloseSeq.current = closeAskSeq;
    // Controlled, the workspace closes the Ask tab itself, and never its own column.
    if (!controlled) setOpen(false);
  }, [closeAskSeq]);

  /* Escape closes, from anywhere on the page while the panel is open — a
   * non-modal panel can be left with focus somewhere else entirely, and Escape
   * should still dismiss it.
   *
   * Two deliberate restraints. It listens in the BUBBLE phase and does not stop
   * propagation, and it yields to the document pane's annotation popup: that
   * popup is a nested dialog whose textarea has focus and its own Escape
   * handler, so a capture-phase swallow here would close the conversation while
   * leaving the popup the user was actually looking at open. Whichever surface
   * the reader is in is the one Escape belongs to. An edit being written keeps
   * its Escape too: it cancels the edit, not the conversation. */
  useEffect(() => {
    // Its own column covers nothing, so Escape has nothing to dismiss there.
    if (!open || railed) return;
    function onKey(event: KeyboardEvent) {
      // Escape inside an IME composition cancels the composition, not the conversation.
      if (event.key !== "Escape" || isImeEnter({ nativeEvent: event, keyCode: event.keyCode })) return;
      const target = event.target;
      if (target instanceof Element
          && target.closest(".ws-annopop, [data-slot='aui_edit-composer']")) return;
      close();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, railed, close]);

  const turnCount = turns.filter((turn) => turn.role === "USER").length;

  return (
    <div className="ws-dock" data-open={open} data-in-tabs={controlled || undefined}>
      {/* Narrow viewports only (CSS): a tap outside closes the sheet, the
          expected touch gesture. Decorative — Escape and the close button are
          the accessible paths, so this carries no role and no name. */}
      {open ? (
        <div className="ws-dock__scrim" onClick={close} aria-hidden="true" />
      ) : null}

      <button
        ref={launcherRef}
        type="button"
        className="ws-dock__launcher"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((wasOpen) => !wasOpen)}
        hidden={open || controlled}
      >
        <IconSparkle size={17} />
        <span className="ws-dock__launcher-text">Ask</span>
        {turnCount > 0 ? (
          <span className="ws-dock__count ws-mono" aria-hidden="true">{turnCount}</span>
        ) : null}
        <span className="ws-visually-hidden">
          {turnCount > 0
            ? ` about this document — ${turnCount} earlier ${turnCount === 1 ? "turn" : "turns"}`
            : " about this document"}
        </span>
      </button>

      {/* Kept MOUNTED while closed so a draft, the restored history and the
          scroll position all survive closing and reopening; `inert` keeps it out
          of the tab order and out of the accessibility tree meanwhile. */}
      <section
        className="ws-dock__panel"
        id={panelId}
        role="dialog"
        aria-modal="false"
        aria-labelledby={titleId}
        aria-hidden={!open}
        inert={!open}
      >
        <header className="ws-dock__head">
          <h2 id={titleId} className="ws-dock__title">
            <IconSparkle size={15} /> Ask about this document
          </h2>
          <button type="button" className="ws-dock__close" onClick={close} aria-label="Close Ask">
            <IconX size={16} />
          </button>
        </header>

        {/* Which document a question will be answered about — stated, never
            assumed. Naming the version is what replaced disabling the input. */}
        <p className="ws-dock__scope">
          {contractId ? (
            <>
              Answers are about <strong>Version {versionNumber}</strong>
              {isLatest ? " (latest)" : ", the version you are reading"}.
            </>
          ) : (
            <>Answers come from the <strong>approved statutes</strong> and the organization&rsquo;s approved positions — cited by Act and section.</>
          )}
        </p>

        {/* This document's chats (`AM-135`) — every one of them is found here. Switching
            waits while an answer is found, so an answer always lands in its own chat. */}
        {contractId ? (
          <div className="ws-dock__chats">
            <label className="ws-visually-hidden" htmlFor={chatsId}>
              Chats about this document
            </label>
            <select id={chatsId} value={conversationId ?? ""} disabled={busy}
                    onChange={(event) => void openChat(event.target.value || null)}>
              {conversationId === null ? <option value="">New chat</option> : null}
              {chats.map((chat) => (
                <option key={chat.id} value={chat.id}>{chatTitle(chat)}</option>
              ))}
            </select>
            <button type="button" className="ws-chat__iconbtn" aria-label="New chat about this document"
                    title="New chat" disabled={busy || conversationId === null}
                    onClick={() => void openChat(null)}>
              <IconPlus size={16} />
            </button>
          </div>
        ) : null}

        <AssistantRuntimeProvider runtime={runtime}>
          <Thread
            empty={!restoring && turns.length === 0 && pending === null}
            // The panel's heading already names it; the welcome says what Ask does here.
            welcome={{ as: "p", title: "Ask what this document says about something. Every"
              + " answer points at the passage it came from — or says plainly that the"
              + " document does not answer it." }}
            suggestions={contractId ? SUGGESTED_QUESTIONS : []}
            onSuggestion={(text) => {
              runtime.thread.composer.setText(text);
              inputRef.current?.focus();
            }}
            renderAnswer={(turn) => {
              const result = answerOf(turn);
              return (
                <>
                  {/* A turn answered from another version says so — its citations
                      cannot highlight on this page. */}
                  {turn.version_number != null && turn.version_number !== versionNumber ? (
                    <p className="ws-dock__turn-version">
                      Answered about Version {turn.version_number}, not the version open now.
                    </p>
                  ) : null}
                  <WsAnswerView result={result} contractId={contractId ?? undefined}
                                openVersionNumber={versionNumber ?? undefined}
                                onOpenVersion={onOpenVersion} />
                  <AnswerMeta turn={result} />
                </>
              );
            }}
            progress={
              <div className="ws-ask__answer" aria-busy="true">
                <p className="ws-pane__note" role="status" aria-live="polite">
                  Looking this up and checking citations…
                </p>
                <span className="ws-skel ws-skel--line" style={{ width: "88%" }} aria-hidden="true" />
                <span className="ws-skel ws-skel--line" style={{ width: "64%" }} aria-hidden="true" />
              </div>
            }
            viewportRef={logRef}
            onJump={() => logRef.current?.focus({ preventScroll: true })}
            composer={{
              inputRef,
              onKeyDown: enterSends(runtime),
              inputId: "ws-ask-question",
              label: "Your question about this document",
              placeholder: contractId ? "Ask about this document…" : "Ask about the law…",
              below: (
                <p className="ws-dock__note">
                  AI answers cite the document, or say they cannot. Verify with the original
                  document.
                </p>
              ),
            }}
          >
            <p className="ws-visually-hidden" role="status" aria-atomic="true">{announce}</p>
            {restoring && turns.length === 0 ? (
              <p className="ws-ask__empty" aria-busy="true">
                Reopening your questions about this document…
              </p>
            ) : null}
            {error ? (
              <div className="ws-state ws-state--error" role="alert">
                <p>{error}</p>
                {failed ? (
                  <button type="button" className="ws-btn ws-btn--sm" disabled={busy}
                          // The edit again only while its question still exists.
                          onClick={() => void submit(failed.text,
                            turns.some((turn) => turn.id === failed.editOf)
                              ? failed.editOf : undefined)}>
                    Try again
                  </button>
                ) : null}
              </div>
            ) : null}
          </Thread>
        </AssistantRuntimeProvider>
      </section>
    </div>
  );
}

/** Prefill chips — editable drafts, exactly like a finding's "Ask about this":
 *  nothing sends until the user sends it. Document-factual questions only. */
const SUGGESTED_QUESTIONS = [
  "What is the termination notice period?",
  "Summarize the payment terms",
  "What are each party's confidentiality obligations?",
  "How can this agreement be renewed or ended?",
];

/** A cited clause of THIS agreement, on the version the answer read, is shown in the
 *  open document — scrolled to and lit by the workspace highlight, the gesture the
 *  numbered citations already use. Any other source (another document, another
 *  version, a standard or a statute) keeps its Sources entry: a highlight that cannot
 *  land would announce a move that never happened. */
export function showInOpenDocument(
  result: Pick<AskResult, "document_version_id">,
  elsewhere: boolean,
  point: (evidenceId: string, source?: string, exact?: boolean) => void,
): ShowInDocument {
  return (source) => {
    const evidence = source.evidence_id;
    if (elsewhere || !evidence || source.kind !== "document"
        || sourceKind(source) !== "This agreement") return undefined;
    if (source.document_version_id && result.document_version_id
        && source.document_version_id !== result.document_version_id) return undefined;
    return () => point(evidence, `source ${source.key}`, true);
  };
}

/** Exported for the static test suite, the `AnswerView` precedent. */
export function WsAnswerView({
  result,
  openVersionNumber,
  onOpenVersion,
  contractId,
}: {
  result: AskResult;
  /** Lets the comparison handoff link to the Findings — a control, not prose. */
  contractId?: string | undefined;
  /** The version the document pane is showing, if the caller knows it. */
  openVersionNumber?: number | undefined;
  onOpenVersion?: ((documentVersionId: string) => void) | undefined;
}) {
  const { point, target } = useHighlight();

  if (result.routed_to_evaluator) {
    return (
      <div className="ws-ask__answer ws-ask__answer--routed" data-state={result.answer_state}>
        <p className="ws-ask__routed-label">Compared by the evaluator, not the assistant</p>
        <AnswerProse text={result.text} />
        <ComparisonHandoff comparison={result.comparison ?? null} contractId={contractId} />
        <PositionsSection positions={result.positions ?? []} contractId={contractId}
          exactTextRequested={result.exact_text_requested ?? false}
          quoteIsTheAnswer={result.quote_is_the_answer ?? false} />
        <StatutesSection statutes={result.statutes ?? null} idPrefix={result.message_id} />
      </div>
    );
  }
  if (result.answer_state !== "ANSWERED") {
    // A refusal is the system working, not failing: quiet, factual, no error tint.
    return (
      <div className="ws-ask__answer ws-ask__answer--refusal" data-state={result.answer_state}>
        <AnswerProse text={result.text} />
      </div>
    );
  }

  /* An evidence row belongs to exactly one version's reading order, so a citation
   * from another version CANNOT be highlighted on the open page. Pointing at it
   * anyway is what the highlight gesture used to do: nothing moved, and the
   * aria-live region announced that something had. Offer the honest action —
   * open the version the answer actually read — instead. */
  const elsewhere =
    openVersionNumber !== undefined &&
    result.version_number !== null &&
    result.version_number > 0 &&
    result.version_number !== openVersionNumber;

  const numbered = citesPositions(result.text, result.citations.length,
    (result.positions ?? []).length);

  return (
    <div className="ws-ask__answer" data-state="ANSWERED">
      <AnswerProse
        text={result.text}
        citeCount={numbered ? (result.positions ?? []).length : result.citations.length}
        citeTargetId={(n) => `${numbered ? "position" : "cite"}-${result.message_id}-${n}`}
        sources={result.sources}
        showInDocument={showInOpenDocument(result, elsewhere, point)}
      />
      {result.citations.length > 0 ? (
        <ol className="ws-ask__citations" aria-label="Sources in this document">
          <li className="ws-ask__routed-label" aria-hidden="true">Sources — this document</li>
          {result.citations.map((citation, index) => (
            <li
              key={citation.chunk_id}
              className="ws-ask__citation"
              id={`cite-${result.message_id}-${index + 1}`}
              tabIndex={-1}
            >
              {elsewhere ? (
                <button
                  type="button"
                  className="ws-ask__cite"
                  onClick={() => result.document_version_id && onOpenVersion?.(result.document_version_id)}
                  disabled={!onOpenVersion}
                  data-evidence-id={citation.evidence_id}
                  data-other-version={result.version_number}
                >
                  <span className="ws-mono">[{index + 1}]</span>{" "}
                  {sectionRef(citation.section_ref) ?? "passage"}
                  {citation.page_number != null ? ` · p.${citation.page_number}` : ""}
                  {" — open Version "}
                  {result.version_number}
                </button>
              ) : (
                <button
                  type="button"
                  className="ws-ask__cite"
                  aria-current={target === citation.evidence_id ? "true" : undefined}
                  onClick={() => point(citation.evidence_id, `citation ${index + 1}`)}
                  data-evidence-id={citation.evidence_id}
                >
                  <span className="ws-mono">[{index + 1}]</span>{" "}
                  {sectionRef(citation.section_ref) ?? "passage"}
                  {citation.page_number != null ? ` · p.${citation.page_number}` : ""}
                </button>
              )}
              <blockquote className="ws-ask__excerpt">{citation.excerpt}</blockquote>
            </li>
          ))}
        </ol>
      ) : null}
      <PositionsSection positions={result.positions ?? []} contractId={contractId}
          exactTextRequested={result.exact_text_requested ?? false}
          quoteIsTheAnswer={result.quote_is_the_answer ?? false}
          idPrefix={numbered ? result.message_id : undefined} />
      <StatutesSection statutes={result.statutes ?? null} idPrefix={result.message_id} />
    </div>
  );
}

/** Domain C — the statute answer, generated over statute evidence only and cited
 *  Act + section (`AM-32` r7). Its own section, never merged with document text. */
export function StatutesSection({
  statutes,
  idPrefix,
}: {
  statutes: AssistStatuteAnswer | null;
  /** Namespaces this section's source ids so a statute marker cannot jump to a
   *  DOCUMENT source of the same number, and so two turns on one page stay apart.
   *  Absent, the markers stay literal text. */
  idPrefix?: string;
}) {
  if (!statutes || statutes.citations.length === 0) return null;
  return (
    <section className="ws-ask__statutes" aria-label="From the approved statute corpus">
      <p className="ws-ask__routed-label">Applicable law — from the approved statute corpus</p>
      {/* The statute answer is generated and renumbered against ITS OWN citation list
          (`service._statute_views` indexes the same `cited` order `_renumber_markers`
          uses), so its markers point here and never at the document's sources. It also
          gets the paragraph handling every other answer has — it was a flat <p>, so a
          two-paragraph statute answer arrived as a wall. */}
      {statutes.text ? (
        <AnswerProse
          text={statutes.text}
          citeCount={idPrefix ? statutes.citations.length : 0}
          citeTargetId={idPrefix ? (n) => `statute-${idPrefix}-${n}` : undefined}
        />
      ) : null}
      <ol className="ws-ask__citations">
        {statutes.citations.map((c, index) => (
          <li
            key={c.statute_chunk_id}
            className="ws-ask__citation"
            id={idPrefix ? `statute-${idPrefix}-${index + 1}` : undefined}
            tabIndex={idPrefix ? -1 : undefined}
          >
            <span className="ws-ask__cite ws-ask__cite--static">
              <span className="ws-mono">[{index + 1}]</span> {c.citation}
              {c.marginal_note ? ` — ${c.marginal_note}` : ""}
            </span>
            <blockquote className="ws-ask__excerpt">{c.excerpt}</blockquote>
          </li>
        ))}
      </ol>
    </section>
  );
}

/** Domain A — the organization's ratified position, quoted verbatim with its own
 *  citation grammar (standard code · source clause), in its own section so it is
 *  never mistaken for document evidence (`AM-32` r1/r4). Says what it is, in words. */
export function PositionsSection({
  positions,
  contractId,
  exactTextRequested = false,
  quoteIsTheAnswer = false,
  idPrefix,
}: {
  positions: AssistPosition[];
  /** Lets the assessment line open the Finding it names — a control, not prose. */
  contractId?: string | undefined;
  /** `AM-76` r2 — the reader asked for the source's own words, which changes the
   *  label. It does NOT decide whether the quote opens: see `quoteIsTheAnswer`. */
  exactTextRequested?: boolean;
  /** `AM-76` r2/r4 — no paraphrase was shown, so the quote is the whole answer and
   *  MUST open. Collapsing it here left the reader a standard code under a sentence
   *  promising the wording was "quoted below". Otherwise the quote stays collapsed:
   *  the answer above is the explanation, and a wall of clause text under every
   *  reply is what `AM-76` supersedes. */
  quoteIsTheAnswer?: boolean;
  /** Set when the answer's markers index these cards (`citesPositions`): each card
   *  shows its number and is the marker's focus target. Absent, no numbers. */
  idPrefix?: string | undefined;
}) {
  if (positions.length === 0) return null;
  // Plural follows the list actually rendered — "the ratified standard" over three
  // of them is the same defect as the collapsed quote, one sentence earlier.
  const noun = positions.length === 1 ? "position" : "positions";
  return (
    <section className="ws-ask__positions" aria-label="Company standard">
      <p className="ws-ask__routed-label">
        {exactTextRequested
          ? "Company standard — the exact wording you asked for"
          : quoteIsTheAnswer
            // No answer was produced, so this claims neither one ("behind this
            // answer") nor relevance — only what is on screen and that it is whole.
            ? `Company standard — the approved ${noun}, quoted in full`
            : `Company standard — the ratified ${noun} behind this answer`}
      </p>
      <ol className="ws-ask__citations">
        {positions.map((position, index) => (
          <li
            key={position.position_chunk_id}
            className="ws-ask__citation"
            id={idPrefix ? `position-${idPrefix}-${index + 1}` : undefined}
            tabIndex={idPrefix ? -1 : undefined}
          >
            <span className="ws-ask__cite ws-ask__cite--static">
              {idPrefix ? <span className="ws-mono">[{index + 1}] </span> : null}
              <span className="ws-mono">{position.standard_code}</span>
              {position.source_clause ? ` · ${position.source_clause}` : ""}
              {` · ${position.document_type}`}
              {position.standard_version != null ? ` · v${position.standard_version}` : ""}
              {/* Status appears ONLY when it is not ACTIVE. Stamping "ACTIVE" on every
                  citation is noise on the common case and trains the eye to skip the
                  field, which is exactly when a DRAFT or DEPRECATED position needs to
                  be noticed. Silence when normal, a word when it matters — not urgency
                  theater, just the fact. `nowrap` keeps the compact label whole, and it
                  is real text, never a hover-only tooltip. */}
              {position.ratification_status && position.ratification_status !== "ACTIVE" ? (
                <span className="ws-ask__standard-state">
                  {position.ratification_status === "DRAFT" ? "Draft" : "Superseded"}
                </span>
              ) : null}
            </span>
            {/* A native <details>, as `EvidenceList` and `EvaluationRow` already use:
                keyboard-operable, correctly announced, and open/closed without a
                custom ARIA widget. `open` is the server's deterministic reading of
                the question (`AM-76` r2 / `AM-109`) — not a guess made here — OR
                `quoteIsTheAnswer` (`AM-76` r4): the fail-closed fallback is exactly
                when the wording must be visible even though it was not asked for.
                Both, not just the wider one, because a caller may set only
                `exactTextRequested` (the backend guarantees the two agree on its
                own r2 path, but the component must not assume every caller does). */}
            <details className="ws-ask__exact" open={exactTextRequested || quoteIsTheAnswer}>
              <summary className="ws-ask__exact-toggle">Exact wording</summary>
              <blockquote className="ws-ask__excerpt">{position.content}</blockquote>
            </details>
            {/* The ASSESSMENT is the deterministic evaluator's existing Finding
                for this standard on the asked version — read, never produced,
                by Ask (`AM-25` r4; the `AM-45` r4 handoff precedent). Absent
                when no Review holds one. Never a score. */}
            {position.finding ? (
              <p className="ws-ask__assessment">
                <span className="ws-ask__routed-label">Assessment — by the evaluator&rsquo;s Finding</span>
                <span
                  className={`ws-chip ws-chip--fill ws-chip--status-${position.finding.user_status.toLowerCase()}`}
                  data-status={position.finding.user_status}
                >
                  {USER_STATUS_LABELS[position.finding.user_status]}
                </span>
                {contractId ? (
                  <Link
                    className="ws-ask__cite"
                    href={`/dashboard?id=${contractId}&finding=${position.finding.finding_id}`}
                  >
                    Open the Finding
                  </Link>
                ) : null}
              </p>
            ) : null}
          </li>
        ))}
      </ol>
    </section>
  );
}

/** The evaluator handoff: the Review that holds the deterministic comparison, with
 *  its Finding counts labelled in words (never colour alone), and a real link. */
export function ComparisonHandoff({
  comparison,
  contractId,
}: {
  comparison: AssistComparison | null;
  contractId?: string | undefined;
}) {
  if (!comparison) {
    return contractId ? (
      <p className="ws-ask__handoff">
        <Link className="ws-btn ws-btn--sm" href={`/dashboard?id=${contractId}`}>
          Open the document to run analysis
        </Link>
      </p>
    ) : null;
  }
  const entries = Object.entries(comparison.findings_by_classification).sort();
  return (
    <div className="ws-ask__handoff">
      <ul className="ws-ask__counts" aria-label="Findings by classification">
        {entries.length === 0 ? <li>No Findings recorded on this Review.</li> : null}
        {entries.map(([classification, count]) => (
          <li key={classification}>
            <span className="ws-mono">{count}</span> {classificationLabel(classification)}
          </li>
        ))}
      </ul>
      {contractId ? (
        <Link
          className="ws-btn ws-btn--sm ws-btn--primary"
          href={`/dashboard?id=${contractId}`}
          data-review-id={comparison.review_id}
        >
          Open the Findings
        </Link>
      ) : null}
    </div>
  );
}
