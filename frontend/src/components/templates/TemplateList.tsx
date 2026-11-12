"use client";

/**
 * Templates (S4, `AM-316`): the library everyone who makes contracts reads — ready to
 * use, awaiting approval — and, for `legal.approve_customization`, the drafts being
 * prepared with what still stands in the way of publishing (the publish gate's check,
 * run once per draft). Plus the home's "Templates to approve" section (Legal only).
 */

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { api, describeError } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import { ACTION } from "@/lib/labels";
import {
  blockers, brandLabel, cardName, clauseNumbers, reviewCopyPath, canPublish, displayTitle, statusWords, templateName,
  templatesFor, within,
  type TemplateCheck, type TemplateDetail, type TemplateSummary,
} from "@/lib/templates";
import { BRANDS, DOC_TYPES, unavailable } from "@/lib/newContract";
import { Dialog } from "@/components/Dialog";
import { UploadContractDialog } from "@/components/workspace/UploadContractDialog";
import { Blocks } from "./TemplateClause";
import { CardDownload, TemplateCard } from "./TemplateCard";
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
  const { can } = useSession();
  const legal = can(P.LEGAL_APPROVE_CUSTOMIZATION);
  const [list, setList] = useState<TemplateSummary[] | null>(null);
  const [checks, setChecks] = useState<Record<string, TemplateCheck | "checking" | "failed">>({});
  const [error, setError] = useState<unknown>(null);
  const [attempt, setAttempt] = useState(0);
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
      // Legal's drafts being prepared: what stands in the way of publishing
      if (attempt === 0 && legal) for (const t of rows.filter((r) => r.status === "DRAFT" && !r.awaiting_approval)) runCheck(t.id);
    }).catch((e) => !cancelled && setError(e));
    return () => { cancelled = true; };
  }, [enabled, legal, runCheck, attempt]);
  return { list, checks, error, runCheck, reload: () => setAttempt((n) => n + 1) };
}

/** The template's full text in a dialog — for a version awaiting approval, which has no
 *  page of its own for anyone but Legal. Marked as a draft; nothing here is usable. */
function PreviewDialog({ t, onClose, returnTo }: {
  t: TemplateSummary; onClose: () => void;
  /** template re-check #1 (WCAG 2.4.3): Esc or Close gives focus back to its Preview button */
  returnTo: () => HTMLElement | null;
}) {
  const [detail, setDetail] = useState<TemplateDetail | null>(null);
  const [error, setError] = useState<unknown>(null);
  useEffect(() => { api.template(t.id).then(setDetail).catch(setError); }, [t.id]);
  const numbers = detail ? clauseNumbers(detail.clauses) : new Map<string, string>();
  return (
    <Dialog onClose={onClose} titleId="tpl-preview-title" overlayClassName="tpl-preview" returnFocus={returnTo}>
      <h2 id="tpl-preview-title">{cardName(t)}</h2>
      <p className="tpl-quiet">Draft, awaiting approval. Not for use with a client.</p>
      <div className="tpl-preview__text">
        {error ? <p className="tpl-error" role="alert">{describeError(error)}</p>
          : !detail ? <p className="tpl-quiet" role="status">Loading the text…</p>
          : detail.clauses.map((c, i) => (
            <section key={c.clause_key} className="tpl-preview__clause" aria-labelledby={`tpl-pv-${i}`}>
              <h3 id={`tpl-pv-${i}`} className="tpl-sheet__title"><span className="tpl-num">{i + 1}</span>{c.title}</h3>
              <div className="tpl-sheet__body"><Blocks blocks={c.body} prefix={String(i + 1)} numbers={numbers} /></div>
            </section>
          ))}
      </div>
      <div className="ws-modal__acts"><button type="button" className="ws-btn" onClick={onClose}>Close</button></div>
    </Dialog>
  );
}

/** Legal's draft rows ("Being prepared"): what still stands in the way of publishing. */
function DraftRows({ rows, checks, runCheck }: {
  rows: TemplateSummary[]; checks: ReturnType<typeof useTemplates>["checks"]; runCheck: (id: string) => void;
}) {
  return (
    <ul className="tpl-cards">
      {rows.map((t) => {
        const got = checks[t.id];
        const check = typeof got === "object" ? got : null;
        const state = got === "checking" || (t.status === "DRAFT" && got === undefined) ? "checking"
          : got === "failed" ? "failed" : "done";
        const ready = canPublish(t, check);
        const action = ready ? "Publish" : ACTION.reviewTemplate;
        return (
          <li key={t.id} className="tpl-card" data-draft>
            <div className="tpl-card__what">
              <h4><Link href={`/templates/${t.id}`}>{cardName(t)}</Link></h4>
              {t.title ? <p className="tpl-card__title">{displayTitle(t.title)}</p> : null}
              <ScBadge readiness={t.special_conditions} />
            </div>
            <div className="tpl-card__state">
              <p className="tpl-card__status">{statusWords(t, check)}</p>
              <p className="tpl-card__why">
                {state !== "done" ? <CheckStatus state={state} onRetry={() => runCheck(t.id)} />
                  : blockers(t, check) ?? "Nothing stands in the way of publishing."}
              </p>
            </div>
            <div className="tpl-card__acts">
              <DownloadMenu path={reviewCopyPath(t)} label="Download review copy" kind="Review copy" />
              <Link className={`ws-btn${ready ? " ws-btn--primary" : ""} tpl-card__act`}
                    href={`/templates/${t.id}`} aria-label={`${action}: ${cardName(t)}`}>{action}</Link>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

/** Templates (`AM-316`): one page for everyone who makes contracts — what is ready to use,
 *  grouped by type and company, and what is awaiting approval (seen, never used); for
 *  Legal also the drafts being prepared and the recommendation. Presentation only: the
 *  server decides who sees and may do what (rule 18). */
export function TemplateLibrary() {
  const { can } = useSession();
  const approver = can(P.LEGAL_APPROVE_CUSTOMIZATION);
  const { list, checks, error, runCheck, reload } = useTemplates(true);
  const [preview, setPreview] = useState<TemplateSummary | null>(null);
  const previewFrom = useRef<HTMLElement | null>(null);
  const [uploading, setUploading] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const published = list?.filter((t) => t.status === "PUBLISHED") ?? [];
  const awaiting = list?.filter((t) => t.awaiting_approval) ?? [];
  const drafts = list?.filter((t) => (t.status === "DRAFT" || t.status === "APPROVED") && !t.awaiting_approval) ?? [];

  function recommend(t: TemplateSummary) {
    setBusy(t.id); setFailure(null);
    api.recommendTemplate(t.id, !t.recommended).then(reload).catch((e) => setFailure(describeError(e)))
      .finally(() => setBusy(null));
  }

  return (
    <div className="lm-page tpl tpl--list">
      <PageHeader title="Templates" meta={<span>Our contracts, ready to fill in. Download a blank one or start a contract from it.</span>} />
      {failure ? <p className="tpl-error" role="alert">{failure}</p> : null}
      {error ? <p className="tpl-error" role="alert">{describeError(error)}</p>
        : !list ? <p className="tpl-quiet" role="status">Loading templates…</p> : (
          <>
            <section className="tpl-lib" aria-labelledby="tpl-ready">
              <h2 id="tpl-ready" className="tpl-lib__h2">Ready to use</h2>
              {DOC_TYPES.slice().reverse().map((type) => (
                <section key={type.id} className="tpl-lib__type" aria-labelledby={`tpl-t-${type.id}`}>
                  <h3 id={`tpl-t-${type.id}`} className="tpl-lib__h3">{type.name}<span>{type.long}</span></h3>
                  {BRANDS.map((brand) => {
                    const cards = templatesFor(published, type.id, brand);
                    const none = unavailable(type.id, brand, published);
                    return (
                      <div key={brand} className="tpl-lib__brand">
                        <h4 className="tpl-lib__h4">{brandLabel(brand)}</h4>
                        {cards.length ? (
                          <div className="tpl-lib__cards">
                            {cards.map((t) => (
                              <TemplateCard key={t.id} t={t} actions={<>
                                <Link className="ws-btn ws-btn--primary" href={`/contracts/new?template=${encodeURIComponent(t.template_key)}`}
                                      aria-label={`Use this template: ${cardName(t)}`}>Use this template</Link>
                                <CardDownload t={t} />
                                {approver ? <>
                                  <button type="button" className="ws-btn" disabled={busy === t.id} aria-pressed={!!t.recommended}
                                          onClick={() => recommend(t)}>
                                    {t.recommended ? "Stop recommending" : "Recommend"}
                                  </button>
                                  <Link className="ws-btn" href={`/templates/${t.id}`} aria-label={`${ACTION.open}: ${cardName(t)}`}>{ACTION.open}</Link>
                                  <ScBadge readiness={t.special_conditions} />
                                </> : null}
                              </>} />
                            ))}
                          </div>
                        ) : none?.startsWith("No CloudPe MSA") ? (
                          <p className="tpl-quiet">{none}</p>
                        ) : (
                          <p className="tpl-lib__none">
                            <span>Being approved by Legal. You can upload a contract instead.</span>
                            <button type="button" className="ws-btn" onClick={() => setUploading(true)}>Upload a contract</button>
                          </p>
                        )}
                      </div>
                    );
                  })}
                </section>
              ))}
            </section>

            {awaiting.length ? (
              <section className="tpl-lib" aria-labelledby="tpl-wait">
                <h2 id="tpl-wait" className="tpl-lib__h2">Awaiting approval</h2>
                <p className="tpl-quiet">Not for use with a client until it is approved. Read it or download the draft.</p>
                <div className="tpl-lib__cards">
                  {awaiting.map((t) => (
                    <TemplateCard key={t.id} t={t} actions={<>
                      <button type="button" className="ws-btn" onClick={(event) => { previewFrom.current = event.currentTarget; setPreview(t); }}
                              aria-label={`Preview: ${cardName(t)}`}>Preview</button>
                      <CardDownload t={t} />
                      {approver ? (
                        <Link className="ws-btn" href={`/templates/${t.id}`}
                              aria-label={`Review and publish: ${cardName(t)}`}>Review and publish</Link>
                      ) : null}
                    </>} />
                  ))}
                </div>
              </section>
            ) : null}

            {approver && drafts.length ? (
              <section className="tpl-lib" aria-labelledby="tpl-prep">
                <h2 id="tpl-prep" className="tpl-lib__h2">Being prepared</h2>
                <p className="tpl-quiet">Only Legal sees these. A template is used for new contracts once every clause is approved and it meets our standards.</p>
                <DraftRows rows={drafts} checks={checks} runCheck={runCheck} />
              </section>
            ) : null}
          </>
        )}
      {preview ? <PreviewDialog t={preview} onClose={() => setPreview(null)} returnTo={() => previewFrom.current} /> : null}
      {uploading ? <UploadContractDialog firstRun={false} onClose={() => setUploading(false)} /> : null}
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
