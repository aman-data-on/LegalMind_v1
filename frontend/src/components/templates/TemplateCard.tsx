"use client";

/**
 * One template as a reader chooses it (`AM-316`) — New contract's step 1 and the
 * Templates page use this one card: its name, what it is for, how many points it sends to
 * Legal on every deal (and which, behind "See the points"), when it was published, and
 * Legal's recommendation or "Awaiting approval" as words. Presentation only: the points
 * are the publish gate's, and Legal decides each on every contract (rule 13).
 */

import { useId, type ReactNode } from "react";

import { shortDate } from "@/components/workspace/model";
import { requirementTitle } from "@/components/workspace/findingLanguage";
import { blankPath, cardName, engineWords, legalLine, reviewCopyPath, type TemplateCardData } from "@/lib/templates";
import { PreviewButton } from "@/components/PreviewPanel";

import "./card.css";

/** The blank (published) or the marked draft (awaiting approval): previewed as the exact
 *  PDF, with Download PDF and Word inside the preview (UX Batch 2, one preview). */
export function CardDownload({ t }: { t: TemplateCardData }) {
  const name = cardName(t);
  return t.awaiting_approval
    ? <PreviewButton path={reviewCopyPath(t)} text="Preview draft" label={`Preview draft: ${name}`}
                     title={`Draft, awaiting approval: ${name}, version ${t.version}`} />
    : <PreviewButton path={blankPath(t)} text="Preview blank" label={`Preview blank: ${name}`}
                     title={`Blank template: ${name}, version ${t.version}`} />;
}

export function TemplateCard({ t, radio, actions }: {
  t: TemplateCardData;
  /** step 1's choice: the card is one radio of a native group */
  radio?: { name: string; checked: boolean; onChange: () => void };
  /** the actions row, after the points (never inside the label) */
  actions?: ReactNode;
}) {
  const id = useId();
  const points = t.known_points;
  const line = legalLine(points);
  const described = [t.purpose && `${id}-p`, line && `${id}-l`, t.recommended && `${id}-r`].filter(Boolean).join(" ");
  const body = (
    <>
      {radio ? (
        <input type="radio" name={radio.name} checked={radio.checked} onChange={radio.onChange}
               aria-labelledby={`${id}-n`} aria-describedby={described || undefined} />
      ) : null}
      <span className="tc__head">
        <span id={`${id}-n`} className="tc__name">{cardName(t)}</span>
        {t.recommended ? <span id={`${id}-r`} className="ws-chip">Legal recommends this one</span> : null}
        {t.awaiting_approval ? <span className="ws-chip">Awaiting approval</span> : null}
      </span>
      {t.purpose ? <span id={`${id}-p`} className="tc__purpose">{t.purpose}</span> : null}
      {line ? <span id={`${id}-l`} className="tc__legal" data-points={points?.length || undefined}>{line}</span> : null}
      <span className="tc__date">
        {t.published_at && !t.awaiting_approval ? `Published ${shortDate(t.published_at)}, version ${t.version}` : `Version ${t.version}`}
      </span>
    </>
  );
  return (
    <div className="tc" data-selected={radio?.checked || undefined} data-choice={radio ? true : undefined}>
      {radio ? <label className="tc__main">{body}</label> : <div className="tc__main">{body}</div>}
      {points?.length ? (
        <details className="tc__points">
          <summary>See the {points.length === 1 ? "1 point" : `${points.length} points`}</summary>
          <ul>
            {points.map((p) => (
              <li key={p.code}>
                <span className="tc__pname">{requirementTitle({ code: p.code, name: p.name ?? null })}</span>
                {p.classification ? <span className="tc__pwhy">{engineWords(p.classification)}</span> : null}
              </li>
            ))}
          </ul>
          <p>Legal decides each one on every contract made from this template.{t.awaiting_approval ? "" : " You can still create it."}</p>
        </details>
      ) : null}
      {actions ? <div className="tc__acts">{actions}</div> : null}
    </div>
  );
}
