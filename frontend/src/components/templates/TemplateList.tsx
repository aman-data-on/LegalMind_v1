"use client";

/**
 * Templates (S4): every template the lawyer governs — brand and type, its status in
 * words, the server's own progress sentence, and what still stands in the way of
 * publishing (from the publish gate's check, run once per draft). Plus the home's
 * "Templates to approve" section. Only for `legal.approve_customization`: for anyone
 * else neither renders (the page shows "not found", the home shows nothing).
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { api, describeError } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import { ACTION } from "@/lib/labels";
import {
  blankPath, blockers, reviewCopyPath, canPublish, displayTitle, isDemo, statusWords, templateName, within,
  DEMO_WORDS,
  type TemplateCheck, type TemplateSummary,
} from "@/lib/templates";
import { PageHeader } from "@/components/page/PageHeader";
import { DownloadMenu } from "./DownloadMenu";
import { IconCheck } from "@/components/workspace/icons";

import "./templates.css";

/** Where the check against our standards stands, with a way to run it again — the list,
 *  the template's header, its side panel and "Before publishing" all say it this way. */
export function CheckStatus({ state, onRetry }: { state: "checking" | "failed" | "done"; onRetry: () => void }) {
  if (state === "checking") return <span role="status">Checking against our standards…</span>;
  if (state === "failed") {
    return (
      <span role="alert">
        Couldn’t check right now —{" "}
        <button type="button" className="ws-linkbtn" onClick={onRetry}>try again</button>
      </span>
    );
  }
  return null;
}

function useTemplates(enabled: boolean) {
  const [list, setList] = useState<TemplateSummary[] | null>(null);
  const [checks, setChecks] = useState<Record<string, TemplateCheck | "checking" | "failed">>({});
  const [error, setError] = useState<unknown>(null);
  const runCheck = useCallback((id: string) => {
    setChecks((m) => ({ ...m, [id]: "checking" }));
    within(api.checkTemplate(id)).then((c) => setChecks((m) => ({ ...m, [id]: c })))
      .catch(() => setChecks((m) => ({ ...m, [id]: "failed" })));
  }, []);
  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    api.templates().then((rows) => {
      if (cancelled) return;
      setList(rows);
      for (const t of rows.filter((r) => r.status === "DRAFT")) runCheck(t.id);
    }).catch((e) => !cancelled && setError(e));
    return () => { cancelled = true; };
  }, [enabled, runCheck]);
  return { list, checks, error, runCheck };
}

export function TemplateList() {
  const { can } = useSession();
  const { list, checks, error, runCheck } = useTemplates(can(P.LEGAL_APPROVE_CUSTOMIZATION));
  const shown = list?.filter((t) => t.status !== "RETIRED") ?? null;
  return (
    <div className="lm-page tpl tpl--list">
      <PageHeader title="Templates"
                  meta={<span>A template is used for new contracts once every clause is approved and it meets our standards.</span>} />
      {error ? <p className="tpl-error" role="alert">{describeError(error)}</p>
        : !shown ? <p className="tpl-quiet" role="status">Loading templates…</p>
        : !shown.length ? <p className="tpl-quiet">No templates have been imported yet.</p> : (
          <ul className="tpl-cards">
            {shown.map((t) => {
              const got = checks[t.id];
              const check = typeof got === "object" ? got : null;
              const state = got === "checking" || (t.status === "DRAFT" && got === undefined) ? "checking"
                : got === "failed" ? "failed" : "done";
              const ready = canPublish(t, check);
              const action = ready ? "Publish" : t.status === "DRAFT" ? ACTION.reviewTemplate : ACTION.open;
              return (
                <li key={t.id} className="tpl-card" data-draft={t.status === "DRAFT" || undefined}>
                  <div className="tpl-card__what">
                    <h2><Link href={`/templates/${t.id}`}>{templateName(t)}</Link></h2>
                    {t.title || t.source_file ? (
                      <p className="tpl-card__title">
                        {[t.title && displayTitle(t.title), t.source_file && `from ${t.source_file}`]
                          .filter(Boolean).join(", ")}
                      </p>
                    ) : null}
                    <ScBadge readiness={t.special_conditions} />
                  </div>
                  <div className="tpl-card__state">
                    <p className="tpl-card__status">{statusWords(t, check)}</p>
                    <p className="tpl-card__why">
                      {t.status !== "DRAFT" ? (isDemo(t) ? DEMO_WORDS : t.progress)
                        : state !== "done" ? <CheckStatus state={state} onRetry={() => runCheck(t.id)} />
                        : blockers(t, check) ?? "Nothing stands in the way of publishing."}
                    </p>
                  </div>
                  <div className="tpl-card__acts">
                    {t.status === "PUBLISHED" ? (
                      <DownloadMenu path={blankPath(t)} label="Download blank template" />
                    ) : t.status === "DRAFT" || t.status === "APPROVED" ? (
                      <DownloadMenu path={reviewCopyPath(t)} label="Download review copy" kind="Review copy" />
                    ) : null}
                    <Link className={`ws-btn${ready ? " ws-btn--primary" : ""} tpl-card__act`}
                          href={`/templates/${t.id}`} aria-label={`${action}: ${templateName(t)}`}>
                      {action}
                    </Link>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
    </div>
  );
}

/** U8: whether agreed changes on a contract made from it can go out as a final contract
 *  with Annexure A. Not set up never stops publishing, so it is said quietly. */
export function ScBadge({ readiness }: { readiness?: TemplateSummary["special_conditions"] }) {
  if (!readiness) return null;
  return (
    <p className="tpl-card__sc" data-ready={readiness.ready || undefined}>
      {readiness.ready ? <><IconCheck size={11} />Annexure A set up</> : "Annexure A not set up"}
    </p>
  );
}

/** The lawyer's home (For my review): the drafts still waiting for approval. */
export function TemplatesToApprove() {
  const { can } = useSession();
  const holder = can(P.LEGAL_APPROVE_CUSTOMIZATION);
  const [drafts, setDrafts] = useState<TemplateSummary[]>([]);
  useEffect(() => {
    if (!holder) return;
    api.templates().then((rows) => setDrafts(rows.filter((t) => t.status === "DRAFT"))).catch(() => setDrafts([]));
  }, [holder]);
  if (!holder || !drafts.length) return null;
  return (
    <section className="ws-hq" aria-labelledby="ws-home-templates">
      <h2 id="ws-home-templates" className="ws-home__qtitle">
        Templates to approve<span className="ws-home__qn">{drafts.length}</span>
      </h2>
      <ul className="ws-hq__list">
        {drafts.map((t) => (
          <li key={t.id} className="ws-hq__item">
            <span className="ws-hq__what">
              <span className="ws-hq__sentence">{templateName(t)}: {t.progress}</span>
              <span className="ws-hq__doc"><span>{statusWords(t, null)}</span></span>
            </span>
            <span className="ws-hq__since" />
            <Link className="ws-btn ws-hq__act" href={`/templates/${t.id}`}
                  aria-label={`${ACTION.reviewTemplate}: ${templateName(t)}`}>{ACTION.reviewTemplate}</Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
