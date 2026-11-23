/**
 * The Changes tab's notes above the list — each one only where it says something true
 * about this pair, in the server's facts: which of our versions the client's is compared
 * with, a side whose Annexure A could not be read, a blank template's link, the changes
 * the client did not mark (R2), and the client's comments on clauses they did not change.
 * Split out of `ChangesPane` (batch 1, redline truth); presentation only.
 */
import { CHANGES_COPY, RETURNED_COPY } from "@/lib/labels";
import { answersAsLegal, clauseName, historyLine, type ChangeList, type ClientChange } from "@/lib/changes";
import { displayTitle } from "@/lib/templates";
import { CommentLines } from "./WordComments";

export function ChangesBanners({ data, allUntracked }: { data: ChangeList; allUntracked: boolean }) {
  const elsewhere = data.comments_elsewhere ?? [];
  return (
    <>
      {data.from ? <p className="cx-banner" role="note">{CHANGES_COPY.comparedWith(data.from.version_number)}</p> : null}
      {data.tracked_base ? <p className="cx-banner" role="note">{RETURNED_COPY.banner}
        {/* item 12: Legal sees why Keep our wording is missing here (AM-459, Q2) */}
        {answersAsLegal(data) ? <><br />{RETURNED_COPY.keepOff}</> : null}</p> : null}
      {data.special_conditions_not_applied?.length ? (
        <div className="cx-banner cx-banner--strong" role="note">
          <strong>Annexure A could not be read on this copy, so each change is compared with the contract text as
            written, and every change goes to Legal.</strong>
          <ul>{data.special_conditions_not_applied.map((why) => <li key={why}>{why.charAt(0).toUpperCase() + why.slice(1)}.</li>)}</ul>
        </div>
      ) : null}
      {data.template ? (
        <p className="cx-banner" role="note">
          Made from our blank template{data.template.title
            ? <> &ldquo;{displayTitle(data.template.title)}&rdquo;</> : null}, version {data.template.version}.
          {" "}Filling in the details is not a change;{" "}
          {data.summary.total ? "every other difference from the template is listed here."
            : "nothing else differs from it."}
          {data.template.message ? <><br /><strong>{data.template.message}</strong></> : null}
        </p>
      ) : null}
      {data.summary.untracked > 0 ? (
        <p className="cx-banner" role="note">
          {allUntracked ? (
            <>{data.summary.total === 1 ? <>This change is not</> : <>None of these <strong>{data.summary.total}</strong> changes is</>} marked in the
              client&rsquo;s file — {data.summary.total === 1 ? "it was" : "they were"} made without tracking. LegalMind found each one
              by comparing the text.</>
          ) : (
            <><strong>{data.summary.untracked}</strong> of {data.summary.total} changes {data.summary.untracked === 1 ? "is" : "are"} not
              marked in the client&rsquo;s file (made without tracking). Each is tagged
              &ldquo;Untracked&rdquo; in the list.</>
          )}
        </p>
      ) : null}
      {elsewhere.length ? (
        <details className="cx-banner cx-elsewhere">
          <summary>{CHANGES_COPY.commentsElsewhere(elsewhere.length)}</summary>
          {elsewhere.map((c, i) => (
            <div key={i} className="ws-row__notes">
              <p className="cx-label">{clauseName(c.clause) || "Unnumbered text"}</p>
              <CommentLines comments={[c]} />
            </div>
          ))}
        </details>
      ) : null}
      {data.answered_earlier?.length ? (
        <div className="cx-banner" role="note">
          {data.answered_earlier.map((a) => <EarlierLine key={a.row_key} answer={a} />)}
        </div>
      ) : null}
    </>
  );
}

/** Ground rule 1: an answer given on an earlier reading of this clause — shown, never
 *  dropped. The row is still to answer on this reading. */
export function EarlierAnswers({ change }: { change: ClientChange }) {
  if (!change.earlier_answers?.length) return null;
  return (
    <div className="cx-section cx-earlier" role="note">
      {change.earlier_answers.map((a) => <EarlierLine key={a.row_key} answer={a} />)}
      <p className="ws-pane__note">{CHANGES_COPY.earlierAnswerHint}</p>
    </div>
  );
}

function EarlierLine({ answer }: { answer: NonNullable<ClientChange["earlier_answers"]>[number] }) {
  // one answer, so its round tag ("R1: ") says nothing here
  return <p><strong>{CHANGES_COPY.earlierAnswer}</strong> {historyLine([answer]).replace(/^R1: /, "")}</p>;
}
