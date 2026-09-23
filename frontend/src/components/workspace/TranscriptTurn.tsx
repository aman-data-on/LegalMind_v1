/**
 * One turn of a recorded Ask conversation — the read-only counterpart of the
 * live AskPane (slice 3). Same registers, same rules:
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

import { sectionRef } from "@/lib/documentTypes";
import type { ConversationTurn } from "@/lib/types";

import { ComparisonTable } from "./ComparisonTable";
import { AnswerProse } from "./AnswerProse";
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

export function TranscriptTurn({
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
          <span className="ws-ask__role">You</span> {turn.content}
        </p>
      </div>
    );
  }

  if (turn.routed_to_evaluator) {
    return (
      <div className="ws-turn">
        <div className="ws-ask__answer ws-ask__answer--routed" data-state={turn.answer_state ?? undefined}>
          <p className="ws-ask__routed-label">Compared by the evaluator, not the assistant</p>
          <p>{turn.content}</p>
          {comparisonReviewId ? (
            <ComparisonTable reviewId={comparisonReviewId} contractId={contractId} />
          ) : null}
          <PositionsSection positions={turn.positions ?? []} contractId={contractId ?? undefined}
            quoteIsTheAnswer={turn.quote_is_the_answer ?? false} />
          <StatutesSection statutes={turn.statutes ?? null} idPrefix={turn.id} />
        </div>
      </div>
    );
  }

  if (turn.answer_state !== "ANSWERED") {
    return (
      <div className="ws-turn">
        <div className="ws-ask__answer ws-ask__answer--refusal" data-state={turn.answer_state ?? undefined}>
          <p>{turn.content}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="ws-turn">
      <div className="ws-ask__answer" data-state="ANSWERED">
        {/* The marker in the prose and the item in the list are one sequence — the
            server renumbered them together after verification — so the marker can
            carry the reader to its source. `turn.id` scopes the DOM id: a transcript
            renders many answers on one page, and "source 1" of the third turn must
            not steal the jump from "source 1" of the first. */}
        <AnswerProse
          text={turn.content}
          citeCount={turn.citations.length}
          citeTargetId={(n) => `cite-${turn.id}-${n}`}
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
                <blockquote className="ws-ask__excerpt">{citation.excerpt}</blockquote>
              </li>
            ))}
          </ol>
        ) : null}
        {/* DD-17 r7 — the ratified position the answer touches, beside it, in its
            own section with its own citation grammar. Read, never produced. */}
        <PositionsSection positions={turn.positions ?? []} contractId={contractId ?? undefined}
            quoteIsTheAnswer={turn.quote_is_the_answer ?? false} />
        <StatutesSection statutes={turn.statutes ?? null} idPrefix={turn.id} />
      </div>
    </div>
  );
}

export { AnswerProse } from "./AnswerProse";
