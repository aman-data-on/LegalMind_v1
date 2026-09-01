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
}: {
  turn: ConversationTurn;
  contractId: string | null;
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
          <p>{turn.content}</p>
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
        <p className="ws-ask__text">{turn.content}</p>
        {turn.citations.length > 0 ? (
          <ol className="ws-ask__citations">
            {turn.citations.map((citation, index) => (
              <li key={citation.chunk_id} className="ws-ask__citation">
                {contractId ? (
                  <Link
                    className="ws-ask__cite"
                    href={`/dashboard?id=${contractId}&evidence=${citation.evidence_id}`}
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
                {citation.retrieval_score != null ? (
                  <span className="ws-ask__score ws-mono">
                    retrieval score {citation.retrieval_score.toFixed(3)}
                  </span>
                ) : null}
              </li>
            ))}
          </ol>
        ) : null}
      </div>
    </div>
  );
}
