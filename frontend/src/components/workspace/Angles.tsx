"use client";

/**
 * The ⚖️ Legal and 💼 Business angles, and the counter-proposal cards (`AM-152`).
 *
 * Everything shown here is built by the SERVER from what the engine already decided —
 * the Findings, the document's own fee and term, the Constitution's own drafting
 * language — so this file renders and never decides (rule 18). One fetch per Review,
 * shared by the Summary, every finding card and the Ask clause view.
 */
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { BusinessPoint, CounterProposal, ReviewAngles } from "@/lib/types";

const cache = new Map<string, Promise<ReviewAngles | null>>();

/** The angles of one Review, fetched once per page; null while loading or unavailable. */
export function useReviewAngles(reviewId: string | null | undefined): ReviewAngles | null {
  const [angles, setAngles] = useState<ReviewAngles | null>(null);
  useEffect(() => {
    if (!reviewId) return;
    let cancelled = false;
    if (!cache.has(reviewId)) {
      // A failure, or a Review with no findings yet (still being analysed), is not
      // kept: the next mount asks again rather than showing an empty angle for good.
      const pending = api.angles(reviewId).catch(() => null);
      cache.set(reviewId, pending);
      void pending.then((value) => {
        if (!value || value.legal.actionable + value.legal.matching === 0) {
          cache.delete(reviewId);
        }
      });
    }
    void cache.get(reviewId)!.then((value) => {
      if (!cancelled) setAngles(value);
    });
    return () => {
      cancelled = true;
    };
  }, [reviewId]);
  return reviewId ? angles : null;
}

/** One business point: the headline, what it means, and the money when the document
 *  states the figures — said in words, never by colour alone. */
function Point({ point }: { point: BusinessPoint }) {
  return (
    <li className="ws-angle__point">
      <p className="ws-angle__headline">{point.headline}</p>
      {point.body ? <p className="ws-angle__body">{point.body}</p> : null}
      {point.money ? <p className="ws-angle__money"><strong>{point.money}</strong></p> : null}
      {point.where ? <p className="ws-angle__where">{point.where}</p> : null}
    </li>
  );
}

/** The Summary's two angles: what the contract commits and the risks that cost most,
 *  then a pointer to the Legal angle below (the status tiles and Findings). */
export function BusinessAngle({ reviewId }: { reviewId: string | null | undefined }) {
  return <BusinessAngleView angles={useReviewAngles(reviewId)} />;
}

export function BusinessAngleView({ angles }: { angles: ReviewAngles | null }) {
  if (!angles || (angles.business.length === 0 && !angles.commercial.committed_value_text)) {
    return null;
  }
  const { commercial: c } = angles;
  const quoted = [c.fee_text, c.term_text].filter(Boolean).map((t) => `“${t}”`).join("; ");
  return (
    <section className="ws-angle" aria-labelledby="ws-angle-business">
      <h3 id="ws-angle-business" className="ws-angle__title">
        <span aria-hidden="true">💼 </span>Business angle
      </h3>
      {c.committed_value_text ? (
        <p className="ws-angle__lede">
          This contract commits <strong>{c.committed_value_text}</strong> of fees
          {c.term_months ? ` over ${c.term_months} months` : ""}
          {c.excludes_gst ? ", excluding GST" : ""} — read from the document’s own
          figures{quoted ? ` (${quoted})` : ""}.
        </p>
      ) : null}
      {angles.top_risks.length > 0 ? (
        <>
          <p className="ws-angle__sub">
            {angles.top_risks.length === 1 ? "The risk" : `The ${angles.top_risks.length} risks`}{" "}
            that cost the most, first:
          </p>
          <ol className="ws-angle__list">
            {angles.top_risks.map((point) => <Point key={point.finding_id} point={point} />)}
          </ol>
        </>
      ) : null}
      <p className="ws-angle__legal">
        <span aria-hidden="true">⚖️ </span>Legal angle below: {angles.legal.actionable}{" "}
        {angles.legal.actionable === 1 ? "point differs" : "points differ"} from our
        standards or could not be read; {angles.legal.matching}{" "}
        {angles.legal.matching === 1 ? "matches" : "match"} them.
      </p>
    </section>
  );
}

/** The counter-proposal card on a deviating finding: the Constitution's own words to
 *  send back, labelled exactly as the Constitution labels them. */
export function CounterProposalCard({ proposal }: { proposal: CounterProposal }) {
  return (
    <aside className="ws-counter" aria-label="Recommended counter-proposal">
      <p className="ws-counter__title">Recommended wording to send back</p>
      <blockquote className="ws-counter__text">{proposal.text}</blockquote>
      <p className="ws-counter__label">{proposal.label}</p>
    </aside>
  );
}

/** A finding card's counter-proposal, when the Review's angles carry one for it. */
export function FindingCounterProposal({ reviewId, findingId }: {
  reviewId: string | null | undefined;
  findingId: string;
}) {
  const angles = useReviewAngles(reviewId);
  const proposal = angles?.counter_proposals[findingId];
  return proposal ? <CounterProposalCard proposal={proposal} /> : null;
}

/** The Ask clause view's business points — only the shown findings' (`AM-149`). */
export function ClauseBusiness({ reviewId, findingIds }: {
  reviewId: string | null | undefined;
  findingIds: string[];
}) {
  const angles = useReviewAngles(reviewId);
  const points = (angles?.business ?? []).filter((p) => findingIds.includes(p.finding_id));
  if (points.length === 0) return null;
  return (
    <section className="ws-angle" aria-label="Business angle">
      <p className="ws-angle__title"><span aria-hidden="true">💼 </span>Business angle</p>
      <ul className="ws-angle__list">
        {points.map((point) => <Point key={point.finding_id} point={point} />)}
      </ul>
    </section>
  );
}

const LEGAL_WORDS: Record<string, string> = {
  DEVIATION: "Deviates from our standard",
  MISSING: "Our standard's clause is missing",
  CONFLICT: "Provisions contradict each other",
  UNABLE_TO_EVALUATE: "A person must read it",
};

/** Under an AI answer: the engine's own findings on the clauses the answer cited — the
 *  ⚖️ Legal and 💼 Business angles and the counter-proposal, built by the server from
 *  the review, never by the model (`AM-152`). Nothing when the answer cited no clause
 *  the review measured. */
export function AnswerAngles({ reviewId, evidenceIds }: {
  reviewId: string | null | undefined;
  evidenceIds: string[];
}) {
  return <AnswerAnglesView angles={useReviewAngles(reviewId)} evidenceIds={evidenceIds} />;
}

export function AnswerAnglesView({ angles, evidenceIds }: {
  angles: ReviewAngles | null;
  evidenceIds: string[];
}) {
  if (!angles || evidenceIds.length === 0) return null;
  const items = (angles.legal.items ?? []).filter(
    (item) => item.evidence_ids.some((id) => evidenceIds.includes(id)));
  if (items.length === 0) return null;
  const ids = items.map((item) => item.finding_id);
  const points = angles.business.filter((p) => ids.includes(p.finding_id));
  return (
    <section className="ws-angle" aria-label="What the review found in these clauses">
      <p className="ws-angle__title"><span aria-hidden="true">⚖️ </span>Legal angle</p>
      <ul className="ws-angle__list">
        {items.map((item) => (
          <li key={item.finding_id} className="ws-angle__point">
            <p className="ws-angle__headline">
              {item.waived ? "The clause waives our position" :
                (LEGAL_WORDS[item.classification] ?? item.classification)}: {item.title}
            </p>
            {item.where ? <p className="ws-angle__where">{item.where}</p> : null}
            {angles.counter_proposals[item.finding_id] ? (
              <CounterProposalCard proposal={angles.counter_proposals[item.finding_id]!} />
            ) : null}
          </li>
        ))}
      </ul>
      {points.length > 0 ? (
        <>
          <p className="ws-angle__title"><span aria-hidden="true">💼 </span>Business angle</p>
          <ul className="ws-angle__list">
            {points.map((point) => <Point key={point.finding_id} point={point} />)}
          </ul>
        </>
      ) : null}
    </section>
  );
}
