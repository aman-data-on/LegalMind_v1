"use client";

/**
 * What the comparison outcomes mean — 2026-09-04.
 *
 * The audit's blunt finding: a first-time legal reader cannot answer "what does
 * DEVIATION mean?" anywhere in the product without asking a colleague. The words are
 * the locked vocabulary (Step 20, `REC-02`) and they stay exactly as they are; what
 * was missing was the sentence beside them.
 *
 * A `<details>` element, deliberately:
 *  - collapsed by default, so it costs a working reviewer nothing;
 *  - native disclosure semantics — keyboard-operable, screen-reader-announced and
 *    focusable with no ARIA of our own and no JavaScript (native platform feature
 *    over a hand-built popover);
 *  - inline in the flow, so it never covers the findings it explains.
 *
 * The copy states what the ENGINE found, never what the reader should conclude
 * (rule 12): "differs from" is a fact, "is unacceptable" would be a legal position,
 * and only a person holding `legal.decision` records one of those.
 */

import { CLASSIFICATION_HELP } from "@/lib/labels";

export function ClassificationGlossary() {
  return (
    <details className="ws-glossary">
      <summary>What do these outcomes mean?</summary>
      <dl className="ws-glossary__list">
        {CLASSIFICATION_HELP.map((entry) => (
          <div key={entry.value} className="ws-glossary__row">
            <dt>
              <span className="ws-chip ws-chip--fill ws-chip--classify-fill">{entry.label}</span>
            </dt>
            <dd>{entry.help}</dd>
          </div>
        ))}
      </dl>
      <p className="ws-pane__note">
        Outcomes are produced by a deterministic engine from the company standard
        published at the time of the analysis. None of them is a legal decision —
        an authorized person records that.
      </p>
    </details>
  );
}
