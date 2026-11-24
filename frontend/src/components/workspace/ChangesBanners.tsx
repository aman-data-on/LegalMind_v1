/**
 * The Changes tab's notes above the list — each one only where it says something true
 * about this pair, in the server's facts: which of our versions the client's is compared
 * with, a side whose Annexure A could not be read, a blank template's link, the changes
 * the client did not mark (R2; batch 8: first, with highlights read, the list and a line
 * for the reply), and the client's comments on clauses they did not change.
 * Split out of `ChangesPane` (batch 1, redline truth); presentation only.
 */
import { CHANGES_COPY, NOT_MARKED_COPY, RETURNED_COPY } from "@/lib/labels";
import { answersAsLegal, clauseName, firstWords, historyLine, notMarkedRows, type ChangeList, type ClientChange } from "@/lib/changes";
import { openChange } from "@/lib/dealBrief";
import { displayTitle } from "@/lib/templates";
import { NotMarked } from "./NotMarked";
import { CommentLines } from "./WordComments";

/** the not-marked banner's links: as many as the brief shows, then "and N more" */
const SHOWN = 6;

export function ChangesBanners({ data }: { data: ChangeList; allUntracked?: boolean }) {
  const elsewhere = data.comments_elsewhere ?? [];
  const unmarked = notMarkedRows(data);
  // round 2: untracked but highlighted — said once when nothing is unmarked
  const lit = data.changes.filter((c) => c.untracked && !c.unmarked).length;
  return (
    <>
      {!unmarked.length && lit ? (
        <p className="cx-banner" role="note">{NOT_MARKED_COPY.allHighlighted(lit, data.summary.total)}</p>
      ) : null}
      {unmarked.length ? (
        <NotMarked count={data.summary.unmarked ?? unmarked.length} total={data.summary.total}
                   highlightsRead={!!data.summary.highlights_read} onOpen={openChange} inline
                   more={Math.max(0, unmarked.length - SHOWN)}
                   // named as the brief names them; the list below tags every one
                   items={unmarked.slice(0, SHOWN).map((c) => ({ rowKey: c.row_key, name: NOT_MARKED_COPY.clause(
                     c.clause.number, c.clause.heading ?? c.clause.name, firstWords(c)) }))} />
      ) : null}
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
      {elsewhere.length ? (
        <details className="cx-banner cx-elsewhere">
          <summary>{CHANGES_COPY.commentsElsewhere(elsewhere.length)}</summary>
          {elsewhere.map((c, i) => (
            <div key={i} className="ws-row__notes">
              <p className="cx-label">{clauseName(c.clause) || CHANGES_COPY.unnumbered}</p>
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
