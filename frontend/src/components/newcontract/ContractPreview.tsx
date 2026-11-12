"use client";

/**
 * The contract as it will read (S5) — set exactly as the template's clause sheet (Page 4:
 * Source Serif, hanging numbers), its wording fixed: there is no editor here at all. Every
 * value a person gives is a button on a soft accent ground that takes them to its
 * question; a field not answered yet stands in the sentence as its named chip. Values are
 * drawn from the reader's own answers as they type, before the save returns; structure
 * (a clause or schedule a condition adds) comes with the server's next preview.
 */

import type { ReactNode } from "react";

import "@/components/templates/templates.css";
import { answered, display, locked, type Answers, type ContractModel, type ModelBlock, type ModelClause,
         type ModelRun, type Question } from "@/lib/newContract";

interface Ctx {
  questions: Map<string, Question>;
  local: Answers;
  /** the question whose value changed last — its runs replay the settle */
  fresh: string | null;
  onJump: (key: string) => void;
}

function Runs({ runs, ctx }: { runs: ModelRun[] | null | undefined; ctx: Ctx }) {
  return (
    <>
      {(runs ?? []).map((run, i) => {
        if ("ref" in run) return <span key={i}>{run.num ?? "a clause not in this contract"}</span>;
        const q = run.var ? ctx.questions.get(run.var) : undefined;
        if (!q || locked(q)) return <span key={i}>{run.t}</span>;
        const value = ctx.local[q.key];
        if (!answered(q, value)) {
          return (
            <button key={i} type="button" className="tpl-field nc-hole" onClick={() => ctx.onJump(q.key)}
                    aria-label={`${q.label}: not filled in yet. Go to the question`}>{q.label}</button>
          );
        }
        const text = display(q, value);
        return (
          <button key={`${i}-${text}`} type="button" className="nc-val" data-fresh={ctx.fresh === q.key || undefined}
                  onClick={() => ctx.onJump(q.key)} aria-label={`${text} — ${q.label}. Go to the question`}>
            {text}
          </button>
        );
      })}
    </>
  );
}

/** A deep number ("2.1.1.1.1") needs a wider gutter than the clause's 2.6em, or it runs into its text. */
const hang = (n: string | undefined) => (n && n.length > 4 ? { paddingLeft: `${(n.length * 0.5 + 0.9).toFixed(1)}em` } : undefined);

function Blocks({ blocks, ctx }: { blocks: ModelBlock[]; ctx: Ctx }): ReactNode {
  return blocks.map((b, i) => {
    if (b.kind === "sub") {
      return (
        <div key={i} className="tpl-sub">
          <p className="tpl-para" style={hang(b.number)}><span className="tpl-num">{b.number}</span>{b.title ? (b.title_style === "bold" ? <strong>{b.title}</strong> : <u>{b.title}</u>) : null}<Runs runs={b.runs} ctx={ctx} /></p>
          {b.body?.length ? <Blocks blocks={b.body} ctx={ctx} /> : null}
        </div>
      );
    }
    if (b.kind === "list") {
      return <ul key={i} className="tpl-items">{(b.items ?? []).map((r, j) => <li key={j}><Runs runs={r} ctx={ctx} /></li>)}</ul>;
    }
    if (b.kind === "table") {
      return (
        <div key={i} className="nc-tablewrap" tabIndex={0} role="region" aria-label="Table, scrolls sideways">
          <table className="tpl-table"><tbody>
            {(b.rows ?? []).map((row, r) => (
              <tr key={r}>{row.map((cell, c) => r === 0
                ? <th key={c} scope="col"><Runs runs={cell} ctx={ctx} /></th>
                : <td key={c}><Runs runs={cell} ctx={ctx} /></td>)}</tr>
            ))}
          </tbody></table>
        </div>
      );
    }
    if (b.kind === "image") return <p key={i} className="tpl-para tpl-para--note">[Picture: {b.alt || "no description"}]</p>;
    if (b.kind === "heading") return <p key={i} className="tpl-para tpl-para--head"><Runs runs={b.runs} ctx={ctx} /></p>;
    return (
      <p key={i} className="tpl-para">
        {b.kind === "definition" && b.term ? <strong>&ldquo;{b.term}&rdquo; </strong> : null}
        <Runs runs={b.runs} ctx={ctx} />
      </p>
    );
  });
}

function Clauses({ clauses, ctx }: { clauses: ModelClause[]; ctx: Ctx }) {
  return clauses.map((c) => (
    <section key={c.clause_key} className="nc-clause">
      <h3 className="tpl-sheet__title nc-clause__title"><span className="tpl-num">{c.number}</span>{c.title}</h3>
      <Blocks blocks={c.body} ctx={ctx} />
    </section>
  ));
}

const EXEC_HEAD = ["Party", "Signatory", "Designation", "Authority"] as const;

export function ContractPreview({ model, questions, local, fresh = null, onJump }: {
  model: ContractModel;
  questions: Question[];
  local: Answers;
  fresh?: string | null;
  onJump: (key: string) => void;
}) {
  const ctx: Ctx = { questions: new Map(questions.map((q) => [q.key, q])), local, fresh, onJump };
  const exec = model.execution;
  // a column the template never fills (no row names it) is left out, not drawn empty
  const cols = EXEC_HEAD.filter((h) => exec.rows.some((row) => row[h.toLowerCase()] != null));
  return (
    <article className="tpl-sheet nc-sheet" aria-label="The contract, as it will read">
      <h2 className="nc-sheet__title">{model.title}</h2>
      <div className="tpl-sheet__body">
        {model.preamble ? <p className="tpl-para nc-flush"><Runs runs={model.preamble} ctx={ctx} /></p> : null}
        {model.parties.length ? (
          <>
            <h3 className="nc-plainhead">Parties</h3>
            {model.parties.map((p, i) => (
              <div key={i} className="nc-party">
                <p className="tpl-para nc-flush"><strong><Runs runs={p.name} ctx={ctx} /></strong> (&ldquo;{p.role}&rdquo;)</p>
                {p.office ? <p className="tpl-para">Registered office: <Runs runs={p.office} ctx={ctx} /></p> : null}
                {p.cin ? <p className="tpl-para">CIN: <Runs runs={p.cin} ctx={ctx} /></p> : null}
              </div>
            ))}
          </>
        ) : null}
        {model.recitals.length ? (
          <>
            <h3 className="nc-plainhead">Recitals</h3>
            {model.recitals.map((r, i) => (
              <p key={i} className="tpl-para nc-recital"><span className="tpl-num">({String.fromCharCode(65 + i)})</span><Runs runs={r} ctx={ctx} /></p>
            ))}
          </>
        ) : null}
        <Clauses clauses={model.body} ctx={ctx} />
        {exec.rows.length ? (
          <>
            <h3 className="nc-plainhead">Execution</h3>
            <div className="nc-tablewrap" tabIndex={0} role="region" aria-label="Execution table, scrolls sideways">
              <table className="tpl-table nc-exec"><tbody>
                <tr>{[...cols, "Signature", ...(exec.seal ? ["Common seal"] : []), ...(exec.witness ? ["Witness"] : [])]
                  .map((h) => <th key={h} scope="col">{h}</th>)}</tr>
                {exec.rows.map((row, i) => (
                  <tr key={i}>
                    {cols.map((h) => <td key={h} data-col={h.toLowerCase()}><Runs runs={row[h.toLowerCase()]} ctx={ctx} /></td>)}
                    <td />{exec.seal ? <td /> : null}{exec.witness ? <td /> : null}
                  </tr>
                ))}
              </tbody></table>
            </div>
          </>
        ) : null}
        {model.schedules.map((s) => (
          <section key={s.key}>
            <h3 className="nc-sheet__title nc-sheet__title--schedule">{s.title}</h3>
            <Clauses clauses={s.clauses} ctx={ctx} />
          </section>
        ))}
      </div>
    </article>
  );
}
