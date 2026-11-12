"use client";

/**
 * Terms in force (`AM-309`, R-9) — `/contracts/{id}/terms`: the signed contract as its
 * signed amendments change it, from `GET /contracts/{id}/effective`. Set on the same
 * sheet as the Document tab (`reading.ts`); a clause an amendment changed carries one
 * quiet line saying which amendment and when, linked to it, with the earlier wording
 * behind a disclosure.
 *
 * The server decides everything: who may read (an unreadable amendment is never named —
 * `by` is absent and the line says "an amendment"), and whether the chain applies. When
 * it cannot, the page says the server's reason and shows no text as "in force" (rule 15).
 * PRESENTATION ONLY: no text is compared or re-read here.
 *
 * `AM-310`: this page IS the conformed copy (research 13 form (c)) — a reading aid that
 * says so on screen and on paper ("Print or save as PDF" prints this page, the line
 * included); never signed, never stamped, never a version of the contract.
 */

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { PageHeader } from "@/components/page/PageHeader";
import { api, ApiError, describeError } from "@/lib/api";
import { contractDisplayName } from "@/lib/labels";
import type { Contract, EffectiveClause, EffectiveText } from "@/lib/types";
import { contractHref, shortDate } from "./model";
import { readingLayout, readingPieces } from "./reading";
import "./changes.css";

type Load =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; contract: Contract | null; text: EffectiveText };

/** `AM-310`: on the page and on every printed copy, in these words (owner, 2026-11-05) */
export const NOT_BINDING = "For reference only, not binding. The agreed contract and its agreed amendments govern.";

const said = (m: string) => m.charAt(0).toUpperCase() + m.slice(1).replace(/\.?$/, ".");

/** "Amendment No. 1, signed 4 Nov 2026" — numbered in signing order among those the reader may open. */
export function amendmentLabel(text: EffectiveText, id: string | undefined) {
  const at = text.amendments.findIndex((a) => a.contract_id === id);
  if (at < 0) return null;
  return { id: id!, label: `Amendment No. ${at + 1}`, signed: shortDate(text.amendments[at]!.signed_at) };
}

function Note({ text, clause, removed = false }: { text: EffectiveText; clause: EffectiveClause; removed?: boolean }) {
  const who = amendmentLabel(text, clause.by);
  const verb = removed ? "Removed" : clause.original === null ? "Added" : "Changed";
  return (
    <p>
      {verb} by {who ? (
        <><Link href={contractHref(who.id)}>{who.label}</Link>, agreed {who.signed}</>
      ) : "an amendment"}
    </p>
  );
}

function Clause({ text, clause, line, first }: {
  text: EffectiveText; clause: EffectiveClause; line: ReturnType<typeof readingLayout>[number] | undefined;
  first: boolean;
}) {
  // an unnumbered part ("MASTER SERVICES AGREEMENT", "WHEREAS") carries its heading as
  // its first line: set that line as the heading, the rest as its text
  const lead = !clause.number && clause.heading && clause.text.startsWith(`${clause.heading}\n`)
    ? clause.heading : null;
  const body = lead ? clause.text.slice(lead.length + 1) : clause.text;
  const { pieces } = readingPieces(body, { lead: line?.lead ?? 0, changes: [], annotations: [], marks: false });
  const hung = !!line && (line.lead > 0 || !!line.num);
  const style = line ? ({ "--indent": `${line.indent}em`, "--hang": `${hung ? line.hang : 0}em` } as React.CSSProperties) : undefined;
  const changed = "original" in clause;
  return (
    <article className="ws-row" data-kind={clause.heading && clause.heading === clause.text ? "heading" : undefined}
             data-shape={line?.shape ?? undefined} data-changed={changed ? "" : undefined}>
      {lead ? <p className={`ws-row__text lm-terms__head${first ? " lm-terms__head--title" : ""}`}>{lead}</p> : null}
      <p className="ws-row__text" style={style} data-hang={hung ? "" : undefined} data-num={line?.num ?? undefined}>
        {pieces.map((piece, i) => {
          let node: React.ReactNode = piece.text;
          if (piece.term) node = <strong className="ws-row__term">{node}</strong>;
          if (piece.lead) node = <span className="ws-row__num">{node}</span>;
          return <span key={i}>{node}</span>;
        })}
      </p>
      {changed ? (
        <div className="ws-row__notes lm-terms__note" style={style}>
          <Note text={text} clause={clause} />
          {clause.original ? (
            <details>
              <summary>Wording before</summary>
              <p className="lm-terms__was">{clause.original}</p>
            </details>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}

export function TermsInForce({ contractId }: { contractId: string }) {
  const [state, setState] = useState<Load>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.effectiveText(contractId), api.contract(contractId).catch(() => null)])
      .then(([text, contract]) => { if (!cancelled) setState({ kind: "ready", text, contract }); })
      .catch((cause) => {
        if (cancelled) return;
        const message = cause instanceof ApiError && cause.status === 404
          ? "This contract was not found, or you do not have access to it."
          : said(describeError(cause));
        setState({ kind: "error", message });
      });
    return () => { cancelled = true; };
  }, [contractId]);

  const name = state.kind === "ready" && state.contract ? contractDisplayName(state.contract.name) : "The contract";
  if (state.kind === "ready") return <TermsView contractId={contractId} contract={state.contract} text={state.text} />;
  return (
    <div className="ws-recordpage lm-terms-page">
      <PageHeader wide title="Terms in force" back={{ href: contractHref(contractId), label: name }} />
      <div className="ws-state" role={state.kind === "error" ? "alert" : "status"}>
        <p>{state.kind === "error" ? state.message : "Reading the terms in force…"}</p>
      </div>
    </div>
  );
}

/** The loaded page — separate so it renders statically in tests. */
export function TermsView({ contractId, contract, text }: {
  contractId: string; contract: Contract | null; text: EffectiveText;
}) {
  const [onlyChanged, setOnlyChanged] = useState(false);
  const current = "clauses" in text.current ? text.current : null;
  const lines = useMemo(() => current ? readingLayout(current.clauses.map((c) => ({
    content: c.text, section_number: c.number, is_heading: !!c.heading && c.heading === c.text }))) : [],
  [current]);
  const name = contract ? contractDisplayName(contract.name) : "The contract";
  const back = { href: contractHref(contractId), label: name };
  const changed = current ? current.clauses.filter((c) => "original" in c).length : 0;
  const removed = current?.removed ?? [];
  const n = text.amendments.length;
  const stage = contract?.negotiation_stage;
  const signedOn = stage?.stage === "SIGNED" ? shortDate(stage.since) : "";
  // AM-318: a Final deal's terms start from its final copy
  const finalOn = stage?.stage === "FINAL" ? shortDate(stage.since) : "";
  const shown = current
    ? current.clauses.map((c, i) => [c, lines[i]] as const).filter(([c]) => !onlyChanged || "original" in c)
    : [];

  return (
    <div className="ws-recordpage lm-terms-page">
      <PageHeader wide title="Terms in force" back={back}
        meta={<span>
          {signedOn ? `Signed on ${signedOn}` : finalOn ? `From the final copy of ${finalOn}` : "As agreed"}
          {n ? `, with ${n === 1 ? "1 amendment" : `${n} amendments`} applied` : ""}
        </span>}
        secondary={current ? (
          <span className="lm-terms__acts">
            {changed ? (
              <button type="button" className="ws-btn" aria-pressed={onlyChanged}
                      onClick={() => setOnlyChanged((v) => !v)}>
                {onlyChanged ? "Show every clause" : "Show changed clauses only"}
              </button>
            ) : null}
            <button type="button" className="ws-btn" onClick={() => window.print()}>Print or save as PDF</button>
          </span>
        ) : null} />

      <div className="lm-terms__body">
        {current ? (
          <div className="lm-terms__summary">
            <p className="lm-terms__binding" role="note">{NOT_BINDING}</p>
            <p>
              {n === 0 ? "No amendment has been agreed. This is the contract as agreed."
                : changed + removed.length === 0 ? "The amendments change no clause."
                : `${changed === 1 ? "1 clause is" : `${changed} clauses are`} changed`
                  + (removed.length ? `, ${removed.length === 1 ? "1 is" : `${removed.length} are`} removed` : "")
                  + ". Each says which amendment changed it."}
            </p>
            {n ? (
              <ol className="lm-terms__amends">
                {text.amendments.map((a) => (
                  <li key={a.contract_id}>
                    <Link href={contractHref(a.contract_id)}>{contractDisplayName(a.name)}</Link>
                    <span>agreed {shortDate(a.signed_at)}</span>
                  </li>
                ))}
              </ol>
            ) : null}
            {removed.length ? (
              <div className="ws-row__notes lm-terms__removed">
                {removed.map((c, i) => (
                  <div key={i}>
                    <p><strong>{c.number ? `Clause ${c.number}` : c.heading ?? "A clause"}</strong></p>
                    <Note text={text} clause={c} removed />
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        ) : (
          // rule 15: the chain could not be applied — say why, and show no text as in force
          <section className="ws-replynote lm-terms__stopped" aria-labelledby="lm-terms-stopped">
            <div className="ws-replynote__text">
              <h2 id="lm-terms-stopped" className="ws-replynote__title">The terms in force can&rsquo;t be shown</h2>
              <p className="ws-replynote__sub">{said("reason" in text.current ? text.current.reason : "")}</p>
              <p className="ws-replynote__sub">
                Nothing is shown as in force until a person checks it. The agreed contract and each
                amendment are unchanged; <Link href={contractHref(contractId)}>open the contract</Link> to
                read it as agreed.
              </p>
            </div>
          </section>
        )}

        {current ? (
          <div className="lm-terms__well">
            <div className="ws-page">
              {shown.map(([c, line], i) => <Clause key={`${c.number}-${i}`} text={text} clause={c} line={line}
                                                     first={i === 0 && !onlyChanged} />)}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
