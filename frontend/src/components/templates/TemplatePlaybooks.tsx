"use client";

/**
 * What we can offer, per published template (`AM-305`) — read-only, for the sales team
 * to learn before a call: each point's opening, how far the deal owner may go and what
 * goes to Legal. Every line is the server's (`GET /templates/{id}/playbook`); a reader
 * without `legal_position.view` gets nothing from the server and sees nothing here.
 */

import { useEffect, useState } from "react";

import { api, describeError } from "@/lib/api";
import { DEMO_WORDS, displayTitle, isDemo, templateName, type TemplateSummary } from "@/lib/templates";
import { PageHeader } from "@/components/page/PageHeader";
import { OfferList, usePlaybook } from "@/components/workspace/OfferPlaybook";
import { CheckStatus } from "./TemplateList";

import "./templates.css";
import "./playbook.css";

function TemplateOffer({ t }: { t: TemplateSummary }) {
  const [attempt, setAttempt] = useState(0);
  const points = usePlaybook("template", t.id, attempt);
  const head = `tpl-offer-${t.id}`;
  return (
    <section className="tpl-offer" aria-labelledby={head}>
      <header className="tpl-offer__head">
        <h2 id={head}>{templateName(t)}</h2>
        <p>{[t.title && displayTitle(t.title), `version ${t.version}`, isDemo(t) && DEMO_WORDS].filter(Boolean).join(", ")}</p>
      </header>
      {points === "loading" ? <p className="tpl-quiet" role="status">Reading the template against our standards…</p>
        : points === "failed" ? <p className="tpl-error"><CheckStatus state="failed" onRetry={() => setAttempt((n) => n + 1)} /></p>
        : points === null ? null
        : <OfferList points={points} id={head} />}
    </section>
  );
}

/** ``header``: the page's own title (the sales view); without it, a section under the
 *  lawyer's template list. */
export function TemplatePlaybooks({ header = false }: { header?: boolean }) {
  const [list, setList] = useState<TemplateSummary[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  useEffect(() => {
    let live = true;
    api.templates().then((rows) => live && setList(rows.filter((r) => r.status === "PUBLISHED")))
      .catch((e) => live && setError(e));
    return () => { live = false; };
  }, []);
  const intro = "How far you can go without Legal on each published template. Anything past these lines goes to Legal.";
  return (
    <div className={header ? "lm-page tpl tpl--list" : "tpl-offers"}>
      {header ? <PageHeader title="What we can offer" meta={<span>{intro}</span>} />
        : <div className="tpl-offers__head"><h2>What we can offer</h2><p>{intro}</p></div>}
      {error ? <p className="tpl-error" role="alert">{describeError(error)}</p>
        : !list ? <p className="tpl-quiet" role="status">Loading templates…</p>
        : !list.length ? <p className="tpl-quiet">No template is published yet.</p>
        : list.map((t) => <TemplateOffer key={t.id} t={t} />)}
    </div>
  );
}
