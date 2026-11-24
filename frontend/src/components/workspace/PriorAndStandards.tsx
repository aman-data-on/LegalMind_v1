"use client";

/**
 * Batch 8, in the deal brief (both personas):
 * - R1.4 (`AM-464`): how many of the client's changes were already in a contract we
 *   signed or finalised with this client — named, dated, and one press away. Information:
 *   Legal still decides every change.
 * - R5.3/R5.4 (`AM-467`, C-34 open): which of our standard sets measured this paper, and,
 *   where our MSA's terms measured paper that is not an MSA, that Legal confirms which
 *   apply. The lawyer also sees each set's source and points under "Legal details".
 * Everything is the server's (rule 18); nothing here is counted or chosen.
 */
import Link from "@/components/AppLink";
import { FileCheck2 } from "lucide-react";

import { formatDate } from "@/lib/dates";
import type { DealBrief } from "@/lib/dealBrief";
import { MEASURED_COPY, PRIOR_COPY } from "@/lib/labels";

import { contractHref } from "./model";
import "./brief.css";

export function AlreadyAgreed({ agreed }: { agreed: NonNullable<DealBrief["already_agreed"]> }) {
  const paper = agreed.contract;
  return (
    <div className="lm-prior" role="note" data-testid="already-agreed">
      <FileCheck2 aria-hidden="true" className="lm-prior__icon" size={16} />
      <div className="lm-prior__text">
        <p className="lm-prior__title">
          {PRIOR_COPY.brief(agreed.count, paper.kind, paper.name, formatDate(paper.agreed_on))}
        </p>
        <p className="lm-prior__hint">{PRIOR_COPY.briefHint(agreed.count)}</p>
        <Link className="ws-linkbtn lm-prior__open" href={contractHref(paper.contract_id)}>
          {PRIOR_COPY.open(paper.kind)}
        </Link>
      </div>
    </div>
  );
}

export function CheckedAgainst({ brief, legal }: {
  brief: Pick<DealBrief, "measured_against" | "measured_against_note">; legal: boolean;
}) {
  const sets = brief.measured_against;
  if (!sets?.length) return null;
  return (
    <div className="lm-measured" data-testid="checked-against">
      <p className="lm-measured__line">
        {MEASURED_COPY.line(sets.map((s) => s.kind))}
        {brief.measured_against_note ? ` ${MEASURED_COPY.otherPaper}` : ""}
      </p>
      {legal ? (
        <details className="lm-measured__details">
          <summary>{MEASURED_COPY.detailsTitle}</summary>
          <ul>
            {sets.filter((s) => s.name).map((s) => (
              <li key={`${s.kind}|${s.name}`}>{MEASURED_COPY.detailsRow(s.name!, s.points ?? 0)}</li>))}
            {brief.measured_against_note ? <li>{MEASURED_COPY.conflict}</li> : null}
          </ul>
        </details>
      ) : null}
    </div>
  );
}
