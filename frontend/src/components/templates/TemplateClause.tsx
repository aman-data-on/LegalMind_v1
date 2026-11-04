"use client";

/**
 * One template clause set as contract text (S4): Source Serif, hanging numbers, a
 * fill-in field as a named chip — [Counterparty name] — so it never reads as contract
 * words yet. The sheet ends on a signature line: "Reference text — not approved by
 * Legal" until a lawyer approves it, then their name and date.
 */

import { approved, approvedLine, fieldLabel, runs, type Block, type TemplateClause } from "@/lib/templates";

export function Runs({ text, numbers }: { text: string; numbers: Map<string, string> }) {
  return (
    <>
      {runs(text).map((run, i) => "text" in run ? <span key={i}>{run.text}</span>
        : "field" in run ? <span key={i} className="tpl-field">{fieldLabel(run.field)}</span>
        : "term" in run ? <strong key={i}>{run.term}</strong>
        : numbers.has(run.xref) ? <span key={i}>{numbers.get(run.xref)}</span>
        : <span key={i} className="tpl-field">a clause not in this template</span>)}
    </>
  );
}

function Blocks({ blocks, prefix, numbers }: { blocks: Block[]; prefix: string; numbers: Map<string, string> }) {
  return (
    <>
      {blocks.map((b, i) => {
        if (b.kind === "sub") {
          const number = `${prefix}.${blocks.slice(0, i + 1).filter((x) => x.kind === "sub").length}`;
          return (
            <div key={i} className="tpl-sub">
              <p className="tpl-para"><span className="tpl-num">{number}</span><Runs text={b.text ?? ""} numbers={numbers} /></p>
              {b.body?.length ? <Blocks blocks={b.body} prefix={number} numbers={numbers} /> : null}
            </div>
          );
        }
        if (b.kind === "list") {
          return <ul key={i} className="tpl-items">{(b.items ?? []).map((t, j) => <li key={j}><Runs text={t} numbers={numbers} /></li>)}</ul>;
        }
        if (b.kind === "table") {
          return (
            <table key={i} className="tpl-table"><tbody>
              {[b.header ?? [], ...(b.rows ?? [])].map((row, r) => (
                <tr key={r}>{row.map((cell, c) => r === 0
                  ? <th key={c} scope="col"><Runs text={cell} numbers={numbers} /></th>
                  : <td key={c}><Runs text={cell} numbers={numbers} /></td>)}</tr>
              ))}
            </tbody></table>
          );
        }
        if (b.kind === "image") return <p key={i} className="tpl-para tpl-para--note">[Picture: {b.alt || "no description"}]</p>;
        if (b.kind === "heading") return <p key={i} className="tpl-para tpl-para--head"><Runs text={b.text ?? ""} numbers={numbers} /></p>;
        return (
          <p key={i} className="tpl-para">
            {b.kind === "definition" && b.term ? <strong>&ldquo;{b.term}&rdquo; </strong> : null}
            <Runs text={b.text ?? ""} numbers={numbers} />
          </p>
        );
      })}
    </>
  );
}

export function ClauseSheet({ clause, number, numbers, label }: {
  clause: TemplateClause; number: string; numbers: Map<string, string>;
  /** the server's DRAFT label, shown verbatim until the clause is approved */
  label: string;
}) {
  return (
    <article className="tpl-sheet" aria-labelledby="tpl-sheet-title">
      <h2 id="tpl-sheet-title" className="tpl-sheet__title">
        <span className="tpl-num">{number}</span>{clause.title}
      </h2>
      <div className="tpl-sheet__body">
        <Blocks blocks={clause.body} prefix={String(number)} numbers={numbers} />
      </div>
      {/* the one memorable element: the clause ends on a signature line */}
      <p className="tpl-sign" data-approved={approved(clause) || undefined} aria-live="polite">
        {approved(clause) ? approvedLine(clause.approval) : clause.label ?? label}
      </p>
      {approved(clause) && clause.approval?.reason ? (
        <p className="tpl-sign__why">Reason: &ldquo;{clause.approval.reason}&rdquo;</p>
      ) : null}
    </article>
  );
}
