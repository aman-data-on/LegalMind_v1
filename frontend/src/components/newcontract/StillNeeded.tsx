"use client";

/**
 * The side panel's "Still needed" (batch 7): Legal's client items with the server's state
 * each, the GST/MCA check, this deal's questions still unanswered, and the checks' warnings.
 * Each row takes the reader to its field. Presentation only (rule 18).
 */

import type { ClientChecklist } from "@/lib/clientDetails";
import { INTAKE_COPY as C } from "@/lib/labels";
import { OURS, type Question } from "@/lib/newContract";
import { IconCheckCircle, IconChevronDown, IconTriangleAlert } from "@/components/workspace/icons";

import { ItemState, warningWords } from "./ClientDetailsCard";

export function StillNeeded({ checklist, dealLeft, dealDone, dealAsked, refused, onClientItem, onQuestion }: {
  checklist: ClientChecklist | null;
  /** this deal's required questions not answered yet */
  dealLeft: Question[];
  dealDone: number;
  dealAsked: number;
  refused: boolean;
  onClientItem: (field: string) => void;
  onQuestion: (key: string) => void;
}) {
  const client = checklist?.applies ? checklist.items.filter((i) => i.n > 1) : [];
  const counts = checklist?.counts;
  // round 2 (lead polish 2): a value read and not yet confirmed is neither filled nor missing
  const readFields = new Set((checklist?.reads ?? []).filter((r) => r.state === "fill").map((r) => r.field));
  return (
    <div className="ic-needed">
      {checklist?.applies ? (() => {
        const heading = (
          <h3 id="ic-n-client" className="ic-needed__h">{C.title}
            {counts ? <span>{checklist.client_ready ? <IconCheckCircle size={14} /> : null}
              {counts.done === counts.needed && checklist.verify_needed && !checklist.verified
                ? C.addedNotChecked(counts.done, counts.needed) : C.added(counts.done, counts.needed)}</span> : null}</h3>
        );
        const rows = (
          <ul className="ic-needed__list">
            {client.map((i) => (
              <li key={i.key}>
                <button type="button" className="ic-needed__row" onClick={() => onClientItem(i.profile_field ?? i.key)}>
                  <span>{C.items[i.key]}</span>
                  {i.status === "missing" && readFields.has(i.profile_field ?? "")
                    ? <span className="ic-state">{C.readState}</span> : <ItemState item={i} refused={refused} />}
                </button>
              </li>
            ))}
            {checklist.verify_needed ? (
              <li>
                <button type="button" className="ic-needed__row" onClick={() => onClientItem("check")}>
                  <span>{C.checkLine}</span>
                  {checklist.verified ? <ItemState item={{ n: 11, key: "check", source: "profile", status: "done" }} refused={refused} />
                    : <span className="ic-state" data-tone={refused ? "refused" : "missing"}>{C.notChecked}</span>}
                </button>
              </li>
            ) : null}
          </ul>
        );
        // benchmark 3: a finished group is one line, opened on demand
        return checklist.client_ready
          ? <details className="ic-needed__done" aria-labelledby="ic-n-client"><summary><IconChevronDown size={16} />{heading}</summary>{rows}</details>
          : <section aria-labelledby="ic-n-client">{heading}{rows}</section>;
      })() : null}
      <section aria-labelledby="ic-n-deal">
        <h3 id="ic-n-deal" className="ic-needed__h">{C.dealTitle}<span>{C.answered(dealDone, dealAsked)}</span></h3>
        {dealLeft.length ? (
          <ul className="ic-needed__list">
            {dealLeft.map((q) => (
              <li key={q.key}>
                <button type="button" className="ic-needed__row" onClick={() => onQuestion(q.key)}>
                  <span>{q.group === OURS ? C.forUs(q.label) : q.label}</span>
                  <ItemState item={{ n: 0, key: q.key, source: "deal", status: "missing" }} refused={refused} />
                </button>
              </li>
            ))}
          </ul>
        ) : <p className="ic-quiet ic-needed__ok"><IconCheckCircle size={16} />{C.nothingLeft}</p>}
      </section>
      {checklist?.warnings.length ? (
        <section aria-labelledby="ic-n-checks">
          <h3 id="ic-n-checks" className="ic-needed__h">{C.checksTitle}</h3>
          {checklist.warnings.map((w) => <p key={w.code} className="ic-warn"><IconTriangleAlert size={14} />{warningWords(w)}</p>)}
        </section>
      ) : null}
    </div>
  );
}
