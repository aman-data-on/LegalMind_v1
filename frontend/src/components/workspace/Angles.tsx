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
import type {
  BusinessPoint, CounterProposal, LegalItem, Observation, ReviewAngles,
} from "@/lib/types";

const cache = new Map<string, Promise<ReviewAngles | null>>();

/** The angles of one Review, fetched once per page; null while loading or unavailable. */
export function useReviewAngles(reviewId: string | null | undefined): ReviewAngles | null {
  // the value is kept WITH its Review: another Review's angles are never shown while
  // this one's are still loading (its ₹ figures would read as this document's)
  const [loaded, setLoaded] = useState<{ id: string; value: ReviewAngles | null } | null>(
    null);
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
      if (!cancelled) setLoaded({ id: reviewId, value });
    });
    return () => {
      cancelled = true;
    };
  }, [reviewId]);
  return reviewId && loaded?.id === reviewId ? loaded.value : null;
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
  // information, never ranked as a risk: the cap, confidentiality, payment (`AM-156` R7)
  const notes = angles.business.filter((point) => point.risk === false);
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
      ) : c.missing ? (
        <p className="ws-angle__lede">No contract value is shown: {c.missing}.</p>
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
      {notes.length > 0 ? (
        <>
          <p className="ws-angle__sub">Also worth knowing:</p>
          <ul className="ws-angle__list">
            {notes.map((point) => <Point key={point.finding_id} point={point} />)}
          </ul>
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

/** How many issues the Legal angle lists before folding the rest away. */
const ISSUES_SHOWN = 5;

function Issue({ item }: { item: LegalItem }) {
  return (
    <li className="ws-angle__point">
      <p className="ws-angle__headline">{item.title}</p>
      {item.action ? <p className="ws-angle__action">{item.action}</p> : null}
      {item.where ? <p className="ws-angle__where">{item.where}</p> : null}
      {item.enforceability ? (
        <p className="ws-angle__note">
          {item.enforceability.section
            ? `Constitution §${item.enforceability.section}: “${item.enforceability.text}”`
            : item.enforceability.text}
        </p>
      ) : null}
    </li>
  );
}

function Noticed({ observation }: { observation: Observation }) {
  return (
    <li className="ws-angle__point">
      <p className="ws-angle__headline">{observation.text}</p>
      {observation.action ? <p className="ws-angle__action">{observation.action}</p> : null}
      {observation.basis ? (
        <blockquote className="ws-angle__basis">
          Constitution §{observation.basis.section}: “{observation.basis.quote}”
        </blockquote>
      ) : null}
    </li>
  );
}

/** The Legal angle (`AM-159`/`AM-160`): one recommendation line, the issues in the order
 *  a person acts on them, what the document says across clauses, and the additional
 *  points folded away. Every word is the server's; nothing here decides anything. */
export function LegalAngle({ reviewId }: { reviewId: string | null | undefined }) {
  return <LegalAngleView angles={useReviewAngles(reviewId)} />;
}

export function LegalAngleView({ angles }: { angles: ReviewAngles | null }) {
  if (!angles) return null;
  const items = angles.legal.items ?? [];
  const structural = angles.observations?.structural ?? [];
  const additional = angles.observations?.additional ?? [];
  if (!angles.recommendation && items.length + structural.length + additional.length === 0) {
    return null;
  }
  const shown = items.slice(0, ISSUES_SHOWN);
  const folded = items.slice(ISSUES_SHOWN);
  return (
    <section className="ws-angle ws-angle--legal" aria-labelledby="ws-angle-legal">
      <h3 id="ws-angle-legal" className="ws-angle__title">
        <span aria-hidden="true">⚖️ </span>Legal angle
      </h3>
      {angles.recommendation ? (
        <p className="ws-angle__recommendation">{angles.recommendation}</p>
      ) : null}
      {shown.length > 0 ? (
        <>
          <p className="ws-angle__sub">What to do, in order:</p>
          <ol className="ws-angle__list">
            {shown.map((item) => <Issue key={item.finding_id} item={item} />)}
          </ol>
          {folded.length > 0 ? (
            <details className="ws-angle__more">
              <summary>{folded.length} more</summary>
              <ol className="ws-angle__list" start={ISSUES_SHOWN + 1}>
                {folded.map((item) => <Issue key={item.finding_id} item={item} />)}
              </ol>
            </details>
          ) : null}
        </>
      ) : null}
      {structural.length > 0 ? (
        <>
          <p className="ws-angle__sub">Across the document:</p>
          <ul className="ws-angle__list">
            {structural.map((o, i) => <Noticed key={`${o.kind}-${i}`} observation={o} />)}
          </ul>
        </>
      ) : null}
      {additional.length > 0 ? (
        <details className="ws-angle__more">
          <summary>Additional points ({additional.length})</summary>
          <ul className="ws-angle__list">
            {additional.map((o, i) => <Noticed key={`${o.kind}-${i}`} observation={o} />)}
          </ul>
        </details>
      ) : null}
    </section>
  );
}

/** The counter-proposal card on a deviating finding: the Constitution's own words to
 *  send back, labelled exactly as the Constitution labels them. */
export function CounterProposalCard({ proposal }: { proposal: CounterProposal }) {
  // a Company Position is our stance, not clause wording: never "send this back" (review,
  // 2026-10-17) — only the Constitution's Drafting Notes are wording to send
  const wording = proposal.kind === "DRAFTING_LANGUAGE";
  return (
    <aside className="ws-counter"
           aria-label={wording ? "Recommended counter-proposal" : "Our position"}>
      <p className="ws-counter__title">
        {wording ? "Recommended wording to send back" : "Our position — no approved wording to send"}
      </p>
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

/** The findings an answer is about: those it cited, kept to the asked topic — or
 *  sharing a clause with one on it — so a "walk away" question never shows an
 *  unrelated payment finding (`AM-156`). With no topic asked, every cited one; with a
 *  topic asked and none of it cited, none. */
export function answerItems(angles: ReviewAngles, evidenceIds: string[],
                            topicCodes: string[] = []): LegalItem[] {
  const cited = (angles.legal.items ?? []).filter(
    (item) => item.evidence_ids.some((id) => evidenceIds.includes(id)));
  if (topicCodes.length === 0) return cited;            // no topic asked: every cited one
  const onTopic = cited.filter((item) => topicCodes.includes(item.requirement_code));
  if (onTopic.length === 0) return [];      // a topic asked, none of it cited: nothing
  const clauses = new Set(onTopic.flatMap((item) => item.evidence_ids));
  return cited.filter((item) => topicCodes.includes(item.requirement_code)
    || item.evidence_ids.some((id) => clauses.has(id)));
}

/** Above an AI answer: what the review found on the asked point — the money and what
 *  to do — built by the server from the Findings, never by the model (`AM-156`). */
export function AnswerLead({ reviewId, evidenceIds, topicCodes }: {
  reviewId: string | null | undefined;
  evidenceIds: string[];
  topicCodes?: string[];
}) {
  return <AnswerLeadView angles={useReviewAngles(reviewId)} evidenceIds={evidenceIds}
                         topicCodes={topicCodes ?? []} />;
}

export function AnswerLeadView({ angles, evidenceIds, topicCodes = [] }: {
  angles: ReviewAngles | null;
  evidenceIds: string[];
  topicCodes?: string[];
}) {
  if (!angles || evidenceIds.length === 0) return null;
  const items = answerItems(angles, evidenceIds, topicCodes);
  if (items.length === 0) return null;
  const points = angles.business.filter((p) => items.some((i) => i.finding_id === p.finding_id));
  const lead = points.find((p) => p.money && p.risk !== false) ?? points[0];
  const first = items.find((i) => i.finding_id === lead?.finding_id) ?? items[0]!;
  return (
    <section className="ws-lead" aria-label="What the review found">
      <p className="ws-lead__line">
        <strong>From the review:</strong> {lead ? lead.headline : first.title}
        {lead?.money ? <> — <strong>{lead.money}</strong></> : null}
      </p>
      {first.action ? <p className="ws-lead__line">{first.action}.</p> : null}
    </section>
  );
}

/** Under an AI answer: the engine's own findings on the clauses the answer cited — the
 *  ⚖️ Legal and 💼 Business angles and the counter-proposal, built by the server from
 *  the review, never by the model (`AM-152`). Nothing when the answer cited no clause
 *  the review measured. */
export function AnswerAngles({ reviewId, evidenceIds, topicCodes }: {
  reviewId: string | null | undefined;
  evidenceIds: string[];
  topicCodes?: string[];
}) {
  return <AnswerAnglesView angles={useReviewAngles(reviewId)} evidenceIds={evidenceIds}
                           topicCodes={topicCodes ?? []} />;
}

export function AnswerAnglesView({ angles, evidenceIds, topicCodes = [] }: {
  angles: ReviewAngles | null;
  evidenceIds: string[];
  topicCodes?: string[];
}) {
  if (!angles || evidenceIds.length === 0) return null;
  const items = answerItems(angles, evidenceIds, topicCodes);
  if (items.length === 0) return null;
  // the same wording once: a §13 card under the notice AND the cure finding said it twice
  const shown = new Set<string>();
  const cardFor = (id: string) => {
    const proposal = angles.counter_proposals[id];
    if (!proposal || shown.has(proposal.text)) return null;
    shown.add(proposal.text);
    return proposal;
  };
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
            {item.action ? <p className="ws-angle__action">{item.action}.</p> : null}
            {(() => {
              const proposal = cardFor(item.finding_id);
              return proposal ? <CounterProposalCard proposal={proposal} /> : null;
            })()}
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
