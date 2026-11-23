"use client";

/**
 * Batch 8 R2.6 (`AM-461`): the changes the client made with no tracked change and no
 * highlight — the first block of the deal brief and of the Changes tab, for sales and
 * Legal alike (it holds no position). Each change opens its row; "Copy line for the
 * reply" copies one plain line that names the clauses (Q8: copied by a person, never
 * sent). Everything counted is the server's (`unmarked`, `highlights_read`, rule 18).
 */
import { useId, useState } from "react";
import { TriangleAlert } from "lucide-react";

import { NOT_MARKED_COPY, plainClauseSigns } from "@/lib/labels";
import { toast } from "@/components/Toast";
import "./brief.css";

export interface NotMarkedItem { rowKey: string; name: string; quote?: string | undefined }

export function NotMarked({ count, total, highlightsRead, items, more = 0, onOpen, inline = false }: {
  count: number; total: number; highlightsRead: boolean; items: NotMarkedItem[]; more?: number;
  onOpen: (rowKey: string) => void;
  /** the Changes tab: every change, names only, flowing in lines (the list is below) */
  inline?: boolean;
}) {
  const id = useId();
  const [failed, setFailed] = useState(false);
  const names = items.map((i) => i.name);
  const line = NOT_MARKED_COPY.line(count, more ? [...names, NOT_MARKED_COPY.more(more)] : names);
  function copy() {
    setFailed(false);
    const done = () => toast(NOT_MARKED_COPY.copied);
    try {
      void navigator.clipboard.writeText(line).then(done, () => setFailed(true));
    } catch {
      setFailed(true);                                // no clipboard here (http, old browser)
    }
  }
  return (
    <div className="lm-notmarked" role="note" aria-labelledby={`${id}-t`} data-testid="not-marked">
      <p id={`${id}-t`} className="lm-notmarked__title">
        <TriangleAlert aria-hidden="true" className="lm-notmarked__icon" size={16} />
        {highlightsRead ? NOT_MARKED_COPY.title(count, total) : NOT_MARKED_COPY.titleOldFile(count, total)}
      </p>
      <p className="lm-notmarked__body">{highlightsRead ? NOT_MARKED_COPY.body : NOT_MARKED_COPY.bodyOldFile}</p>
      <ul className={inline ? "lm-notmarked__list lm-notmarked__list--inline" : "lm-notmarked__list"}>
        {items.map((i) => (
          <li key={i.rowKey}>
            <button type="button" className="ws-linkbtn lm-notmarked__open" title={i.name} onClick={() => onOpen(i.rowKey)}>{i.name}</button>
            {i.quote ? <> <q className="lm-notmarked__quote">{plainClauseSigns(i.quote)}</q></> : null}
          </li>
        ))}
      </ul>
      {more ? <p className="lm-notmarked__more">{NOT_MARKED_COPY.more(more)}</p> : null}
      <button type="button" className="ws-btn ws-btn--sm lm-notmarked__copy" onClick={copy}>{NOT_MARKED_COPY.copy}</button>
      {failed ? (
        <div className="lm-notmarked__fallback" role="alert">
          <label htmlFor={`${id}-l`}>{NOT_MARKED_COPY.copyFailed}</label>
          <textarea id={`${id}-l`} readOnly rows={3} value={line} onFocus={(e) => e.currentTarget.select()} />
        </div>
      ) : null}
    </div>
  );
}
