/**
 * One turn of an Ask conversation, recorded or just arrived (the workspace draws
 * both through this). Same registers, same rules as the dock's live answer:
 *
 *   USER                 the question, plainly attributed
 *   routed_to_evaluator  the routing note — a pointer, never an answer
 *   refusal states       the identical quiet sentence the live pane showed
 *                        (`AM-29` r4: the record must not become the oracle
 *                        the live wording refuses to be)
 *   ANSWERED             prose plus the SAME citations the live answer carried
 *                        (`AM-25` r5) — here each citation is a real link into
 *                        the document workspace's highlight (`?evidence=`),
 *                        because the transcript lives on its own page
 *
 * A retrieval score renders only when the replay carries one, labeled as
 * exactly that — never confidence (AI-03 item 16; rule 12).
 */

import Link from "next/link";
import { memo, useEffect, useId, useState } from "react";

import { feedback, type FeedbackKind } from "@/lib/api";
import { sectionRef } from "@/lib/documentTypes";
import type { ConversationTurn } from "@/lib/types";

import { ComparisonTable } from "./ComparisonTable";
import { AnswerMeta, AnswerProse, citesPositions } from "./AnswerProse";
import { PositionsSection, StatutesSection } from "./AskDock";

/** The parameter is named `ref` rather than `sectionRef` so it does not shadow
 *  the shared helper — that shadowing is how this file kept its own `§` prefix
 *  when the other five callers were converted. */

function citeLabel(ref: string | null, pageNumber: number | null): string {
  return (
    (sectionRef(ref) ?? "passage") +
    (pageNumber != null ? ` · p.${pageNumber}` : "")
  );
}

/** Memoized: the workspace re-renders on every keystroke in the composer, and without
 *  this every turn re-parsed its whole answer each time — 4.6 s to type 300 characters
 *  in a 24-turn chat (measured 2026-10-06). A turn's props are stable between answers. */
export const TranscriptTurn = memo(function TranscriptTurn({
  turn,
  contractId,
  comparisonReviewId,
}: {
  turn: ConversationTurn;
  contractId: string | null;
  /** The Review holding the deterministic comparison this turn was routed to
   *  (2026-09-11). Present only on a routed turn whose Review is known; the
   *  table it renders is the evaluator's own Findings, never generated here. */
  comparisonReviewId?: string | null;
}) {
  if (turn.role === "USER") {
    return (
      <div className="ws-turn ws-turn--user">
        <p className="ws-ask__q">
          <span className="ws-ask__role ws-visually-hidden">You</span> {turn.content}
        </p>
      </div>
    );
  }

  if (turn.routed_to_evaluator) {
    return (
      <div className="ws-turn ws-turn--ai">
        <AiVoice />
        <div className="ws-ask__answer ws-ask__answer--routed" data-state={turn.answer_state ?? undefined}
             {...signalsOn(turn.id)}>
          <p className="ws-ask__routed-label">Compared by the evaluator, not the assistant</p>
          <AnswerProse text={turn.content} />
          {comparisonReviewId ? (
            <ComparisonTable reviewId={comparisonReviewId} contractId={contractId} />
          ) : null}
          <PositionsSection positions={turn.positions ?? []} contractId={contractId ?? undefined}
          exactTextRequested={turn.exact_text_requested ?? false}
          quoteIsTheAnswer={turn.quote_is_the_answer ?? false} />
          <StatutesSection statutes={turn.statutes ?? null} idPrefix={turn.id} />
        </div>
        <AnswerMeta turn={turn} />
        <AnswerFeedback messageId={turn.id} />
      </div>
    );
  }

  if (turn.answer_state !== "ANSWERED") {
    return (
      <div className="ws-turn ws-turn--ai">
        <AiVoice />
        {/* Every answer through the one renderer: a turn recorded without an answer
            state still carries its formatting, and must not show raw `**` marks. */}
        <div className="ws-ask__answer ws-ask__answer--refusal" data-state={turn.answer_state ?? undefined}
             {...signalsOn(turn.id)}>
          <AnswerProse text={turn.content} />
        </div>
        <AnswerMeta turn={turn} />
        <AnswerFeedback messageId={turn.id} />
      </div>
    );
  }

  const numbered = citesPositions(turn.content, turn.citations.length,
    (turn.positions ?? []).length);

  return (
    <div className="ws-turn ws-turn--ai">
      <AiVoice />
      <div className="ws-ask__answer" data-state="ANSWERED" {...signalsOn(turn.id)}>
        {/* The marker in the prose and the item in the list are one sequence — the
            server renumbered them together after verification — so the marker can
            carry the reader to its source. `turn.id` scopes the DOM id: a transcript
            renders many answers on one page, and "source 1" of the third turn must
            not steal the jump from "source 1" of the first. */}
        <AnswerProse
          text={turn.content}
          citeCount={numbered ? (turn.positions ?? []).length : turn.citations.length}
          citeTargetId={(n) => `${numbered ? "position" : "cite"}-${turn.id}-${n}`}
          sources={turn.sources}
          contractId={contractId}
        />
        {turn.citations.length > 0 ? (
          <ol className="ws-ask__citations" aria-label="Sources in this document">
            <li className="ws-ask__routed-label" aria-hidden="true">Sources — this document</li>
            {turn.citations.map((citation, index) => (
              <li
                key={citation.chunk_id}
                className="ws-ask__citation"
                id={`cite-${turn.id}-${index + 1}`}
                /* Focusable only by script: the marker moves focus here so the jump
                   lands for a keyboard and a screen reader, while Tab still walks the
                   links inside rather than stopping on every source. */
                tabIndex={-1}
              >
                {contractId ? (
                  <Link
                    className="ws-ask__cite"
                    /* The link carries the VERSION the answer was read from
                     * (2026-09-02). Without it the workspace opens on the
                     * newest version, and an `evidence_id` belongs to exactly
                     * one version's reading order — so a citation from an
                     * earlier version used to land on a page that does not
                     * contain the row, and nothing highlighted. */
                    href={
                      `/dashboard?id=${contractId}` +
                      (turn.document_version_id ? `&version=${turn.document_version_id}` : "") +
                      `&evidence=${citation.evidence_id}`
                    }
                    data-evidence-id={citation.evidence_id}
                  >
                    <span className="ws-mono">[{index + 1}]</span> {citeLabel(citation.section_ref, citation.page_number)}
                  </Link>
                ) : (
                  <span className="ws-ask__cite">
                    <span className="ws-mono">[{index + 1}]</span> {citeLabel(citation.section_ref, citation.page_number)}
                  </span>
                )}
                {/* The passage is here to check the answer against, not to read
                    first: four excerpts in full under every reply made the answer
                    the smallest thing on the screen (owner, 2026-09-28). */}
                <details className="ws-ask__passage">
                  <summary>Show the passage</summary>
                  <blockquote className="ws-ask__excerpt">{citation.excerpt}</blockquote>
                </details>
              </li>
            ))}
          </ol>
        ) : null}
        {/* DD-17 r7 — the ratified position the answer touches, beside it, in its
            own section with its own citation grammar. Read, never produced. */}
        <PositionsSection positions={turn.positions ?? []} contractId={contractId ?? undefined}
          exactTextRequested={turn.exact_text_requested ?? false}
          quoteIsTheAnswer={turn.quote_is_the_answer ?? false}
          idPrefix={numbered ? turn.id : undefined} />
        <StatutesSection statutes={turn.statutes ?? null} idPrefix={turn.id} />
      </div>
      <AnswerMeta turn={turn} />
      <AnswerFeedback messageId={turn.id} />
    </div>
  );
});

/** The answer's voice line — a monogram and the product's name — so a reader tells
 *  the two speakers apart at a glance without a frame around either. A monogram, not a
 *  sparkle: DESIGN.md rules sparkle icons out because they read as "an AI-generated
 *  result", which `AI-01` forbids this interface from implying. */
export function AiVoice() {
  return (
    <p className="ws-ask__voice" aria-hidden="true">
      <span className="ws-ask__voicemark">L</span> LegalMind
    </p>
  );
}

/** Each implicit kind already sent per answer on this page: the server keeps one row
 *  per kind anyway, so a repeat would only spend the reader's rate-limit budget — the
 *  same budget their explicit rating draws on. */
const sent = new Set<string>();

/** Sent and forgotten: an implicit signal shows nothing, never retries, never repeats. */
function signal(messageId: string, kind: FeedbackKind) {
  const key = `${messageId}:${kind}`;
  if (sent.has(key)) return;
  sent.add(key);
  void feedback(messageId, kind).catch(() => undefined);
}

/** Opening one of the answer's sources: a link into the document, an in-prose marker,
 *  a Sources-legend entry, or a cited passage. */
const CITATION = "a.ws-ask__cite, .ws-ask__ref, .ws-ask__key, .ws-ask__srcbtn, " +
  ".ws-ask__passage > summary";

/** The implicit signals on an answer's own region (`AM-123`, owner D2c): copying from
 *  it, and opening one of its sources. No UI — one delegated listener per answer, so
 *  the citation components stay as they are. */
export function signalsOn(messageId: string) {
  return {
    onCopy: () => signal(messageId, "COPY"),
    onClick: (event: { target: EventTarget | null }) => {
      if ((event.target as Element | null)?.closest?.(CITATION)) signal(messageId, "CITE_CLICK");
    },
  };
}

/** Leaving a verified answer this soon after it appeared is a negative signal. */
export const QUICK_CLOSE_MS = 5000;

export function closedQuickly(shownAt: number, now: number): boolean {
  return now - shownAt < QUICK_CLOSE_MS;
}

/** `AM-123` quick-close: the reader leaves a verified answer — another chat, a new chat,
 *  another page, or closes the tab — within `QUICK_CLOSE_MS` of it rendering. Leaving
 *  by following one of the answer's own sources is not a quick close. The chat's own
 *  address being set after its first answer is not leaving it. Plain, so it is tested
 *  without a DOM; `useQuickClose` only wires it to the page. */
export function quickCloser(now: () => number = Date.now) {
  let shown: { id: string; chat: string; at: number } | null = null;
  const leave = () => {
    const s = shown;
    shown = null;
    if (s && closedQuickly(s.at, now()) && !sent.has(`${s.id}:CITE_CLICK`)) {
      signal(s.id, "QUICK_CLOSE");
    }
  };
  return {
    /** Marks an answer as just shown in its chat. */
    show: (id: string, chat: string) => { shown = { id, chat, at: now() }; },
    /** The chat on screen is now `activeId`. */
    chat: (activeId: string | null) => { if (shown && shown.chat !== activeId) leave(); },
    leave,
  };
}

/** Returns the call that marks an answer as just shown in its chat. */
export function useQuickClose(activeId: string | null) {
  const [closer] = useState(() => quickCloser());
  useEffect(() => { closer.chat(activeId); }, [activeId, closer]);
  useEffect(() => {
    window.addEventListener("pagehide", closer.leave);
    return () => {
      window.removeEventListener("pagehide", closer.leave);
      closer.leave();
    };
  }, [closer]);
  return closer.show;
}

type RatingState = {
  rating: "UP" | "DOWN" | null;
  status: "" | "saving" | "Recorded" | "Not recorded. Try again.";
  reasonSent: boolean;
};

/** One rating click. The pressed state and "Recorded" are set only after the server has
 *  the record — never before, never on a refusal. Pressing the already-recorded rating
 *  again sends nothing, so a reason already sent is never re-asked for. */
export async function sendRating(messageId: string, current: RatingState,
                                 next: "UP" | "DOWN", why: string | undefined,
                                 set: (patch: Partial<RatingState>) => void) {
  if (next === current.rating && why === undefined) return;
  set({ status: "saving" });
  try {
    await feedback(messageId, "RATING", next, why);
    set({ rating: next, reasonSent: why !== undefined, status: "Recorded" });
  } catch {
    set({ status: "Not recorded. Try again." });
  }
}

/**
 * The reader's own rating of one answer (`AM-123`, owner D2c 2026-10-08; DD-26). Two
 * plain words, never a score: the pressed state and "Recorded" appear only once the
 * server has the record — nothing optimistic, no counts, nothing that says the system
 * learns from it, because it does not (`AM-26`). A reason is asked for only after
 * "Not helpful", and is optional.
 */
export function AnswerFeedback({ messageId }: { messageId: string }) {
  const [state, setState] = useState<RatingState>(
    { rating: null, status: "", reasonSent: false });
  const [reason, setReason] = useState("");
  const reasonId = useId();
  const { rating, status, reasonSent } = state;
  const saving = status === "saving";

  function send(next: "UP" | "DOWN", why?: string) {
    return sendRating(messageId, state, next, why,
                      (patch) => setState((previous) => ({ ...previous, ...patch })));
  }

  return (
    <div className="ws-ask__meta">
      <div className="ws-filter" role="group" aria-label="Rate this answer">
        <button type="button" aria-pressed={rating === "UP"} disabled={saving}
                onClick={() => void send("UP")}>Helpful</button>
        <button type="button" aria-pressed={rating === "DOWN"} disabled={saving}
                onClick={() => void send("DOWN")}>Not helpful</button>
        <span role="status">{saving ? "" : status}</span>
      </div>
      {rating === "DOWN" && !reasonSent ? (
        <form className="ws-field" onSubmit={(event) => {
          event.preventDefault();
          if (reason.trim()) void send("DOWN", reason.trim());
        }}>
          <label className="ws-field__label" htmlFor={reasonId}>
            What was wrong or missing? (optional)
          </label>
          <input id={reasonId} type="text" maxLength={500} value={reason}
                 onChange={(event) => setReason(event.target.value)} />
          <button type="submit" className="ws-btn ws-btn--sm"
                  disabled={saving || !reason.trim()}>Send reason</button>
        </form>
      ) : null}
    </div>
  );
}

export { AnswerProse } from "./AnswerProse";
