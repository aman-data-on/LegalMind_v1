"use client";

/**
 * Legal's choices on a template version not yet published (`AB-209`): keep the approved
 * words as written although the check finds something about the words themselves
 * (`AM-390`), who signs for us (`AM-391`), and which blanks in the approved words sales
 * fills on every deal (`AM-392`). The server decides and refuses; this only asks and shows.
 * Also the Special Conditions readiness (`AM-307`), moved here unchanged.
 */

import { useState } from "react";

import { api, describeError } from "@/lib/api";
import { formatDate } from "@/lib/dates";
import { blockerText } from "@/lib/package";
import {
  displayTitle, type KeptItem, type SpecialConditionsReadiness, type TemplateBlank, type TemplateDetail,
} from "@/lib/templates";

/** Send ``run``; on failure keep the form open with the server's words. */
function useSend(onDone: () => Promise<void>) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const send = async (run: () => Promise<unknown>) => {
    setBusy(true); setError(null);
    try { await run(); await onDone(); return true; }
    catch (e) { setError(describeError(e)); return false; }
    finally { setBusy(false); }
  };
  return { busy, error, send };
}

/** `AM-397`: Annexure 1 — Service Order Form on this version: the services, fees and
 *  initial term sales answers, and the signature page after the annexures. The annexure's
 *  own words are Legal's to supply; until then Final is blocked (the server says so). */
export function OrderForm({ detail, onDone }: { detail: TemplateDetail; onDone: () => Promise<void> }) {
  const { busy, error, send } = useSend(onDone);
  const added = detail.variables.some((v) => v.key === "services" && v.group === "Order form");
  return (
    <div className="tpl-pubgroup"><h3>Annexure 1 — Service Order Form</h3>
      {added ? (
        <p className="tpl-help">Added. Sales picks the services, the fees for each and the initial term when making a
          contract. The annexure&apos;s own wording is still yours to supply: a final contract cannot be made until
          then.</p>
      ) : (
        <>
          <p className="tpl-help">Add the order form: sales then picks the services, the fees and the initial term, and
            the final contract reads MSA, Annexure 1, Annexure 2, then the signature page. No wording is added: the
            annexure&apos;s words stay yours to supply.</p>
          {error ? <p className="tpl-error" role="alert">{error}</p> : null}
          <button type="button" className="ws-btn" disabled={busy}
                  onClick={() => void send(() => api.addAnnexure1(detail.id))}>
            {busy ? "Adding…" : "Add Annexure 1"}
          </button>
        </>
      )}
    </div>
  );
}

/** "Keep as written" on one check finding about the approved words, with a reason. */
export function KeepAsWritten({ templateId, keep, onDone }: {
  templateId: string; keep: { code: string; detail: string }; onDone: () => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const { busy, error, send } = useSend(onDone);
  if (!open) {
    return <button type="button" className="tpl-link" onClick={() => setOpen(true)}>Keep as written</button>;
  }
  const id = `tpl-keep-${keep.detail.length}-${keep.code}`;
  return (
    <form className="tpl-form" onSubmit={(e) => {
      e.preventDefault();
      if (reason.trim()) void send(() => api.keepAsWritten(templateId, keep.code, keep.detail, reason.trim()));
    }}>
      <label htmlFor={id} className="tpl-label">Why keep these words as they are?</label>
      <textarea id={id} className="tpl-reason" rows={2} maxLength={2000} value={reason} required
                aria-describedby={`${id}-help`} onChange={(e) => setReason(e.target.value)} />
      <p id={`${id}-help`} className="tpl-help">For example: &ldquo;Our signed MSA uses this word as it is.&rdquo;
        Your name, the date and the reason are kept on record. Publishing is no longer stopped by this.</p>
      {error ? <p className="tpl-error" role="alert">{error}</p> : null}
      <div className="tpl-actions__row">
        <button type="button" className="ws-btn" onClick={() => setOpen(false)}>Cancel</button>
        <button type="submit" className="ws-btn ws-btn--primary" disabled={busy || !reason.trim()}>
          {busy ? "Keeping…" : "Keep as written"}</button>
      </div>
    </form>
  );
}

export function KeptGroup({ kept }: { kept: KeptItem[] | undefined }) {
  if (!kept?.length) return null;
  return (
    <div className="tpl-pubgroup"><h3>Kept as written <span>{kept.length}</span></h3>
      <p className="tpl-help">Legal chose to keep these words as approved. They do not stop publishing.</p>
      <ul>{kept.map((k) => (
        <li key={`${k.code}-${k.detail}`}><span className="tpl-pubrow__what">{k.detail}</span>
          <span className="tpl-pubrow__said">Kept by {k.by ?? "Legal"}, {formatDate(k.at)}: {k.reason}</span></li>
      ))}</ul></div>
  );
}

const ROLES = { name: "our_signatory_name", designation: "our_signatory_designation", email: "our_signatory_email" } as const;

/** Who signs for us on every contract from this template (`AM-391`). */
export function OurSignatory({ detail, onDone }: { detail: TemplateDetail; onDone: () => Promise<void> }) {
  const byRole = (r: string) => detail.variables.find((v) => (v.role ?? v.key) === r);
  const fields = Object.entries(ROLES).map(([f, r]) => [f, byRole(r)] as const);
  const set = fields.every(([, v]) => typeof v?.locked_value === "string");
  const start = Object.fromEntries(fields.map(([f, v]) => [f, typeof v?.locked_value === "string" ? v.locked_value : ""]));
  const [form, setForm] = useState<Record<string, string>>(start);
  const [editing, setEditing] = useState(!set);
  const { busy, error, send } = useSend(onDone);
  if (fields.some(([, v]) => !v)) return null;           // this template has no signatory fields
  const labels: Record<string, string> = { name: "Name", designation: "Designation", email: "Email" };
  return (
    <div className="tpl-pubgroup"><h3>Who signs for us</h3>
      {!editing ? (
        <>
          <p className="tpl-help">Every contract from this template shows this person on the signature page. Sales cannot
            change it. To use someone else, change it here before publishing.</p>
          <p className="tpl-pubrow__what">{start.name}, {start.designation}, {start.email}</p>
          <button type="button" className="ws-btn" onClick={() => setEditing(true)}>Change signatory</button>
        </>
      ) : (
        <form className="tpl-form" onSubmit={(e) => {
          e.preventDefault();
          void send(() => api.setOurSignatory(detail.id, { name: form.name!.trim(), designation: form.designation!.trim(),
                                                         email: form.email!.trim() })).then((ok) => ok && setEditing(false));
        }}>
          <p className="tpl-help">Not set yet, so sales types it on every new contract. Set it once here and it goes on the
            signature page of every contract from this template.</p>
          {fields.map(([f]) => (
            <div key={f} className="tpl-form">
              <label htmlFor={`tpl-sig-${f}`} className="tpl-label">{labels[f]}</label>
              <input id={`tpl-sig-${f}`} className="tpl-reason" type={f === "email" ? "email" : "text"} required
                     maxLength={200} value={form[f] ?? ""} onChange={(e) => setForm({ ...form, [f]: e.target.value })} />
            </div>
          ))}
          {error ? <p className="tpl-error" role="alert">{error}</p> : null}
          <div className="tpl-actions__row">
            {set ? <button type="button" className="ws-btn" onClick={() => setEditing(false)}>Cancel</button> : null}
            <button type="submit" className="ws-btn" disabled={busy}>{busy ? "Saving…" : "Save signatory"}</button>
          </div>
        </form>
      )}
    </div>
  );
}

function BlankRow({ templateId, where, blank, onDone }: {
  templateId: string; where: string; blank: TemplateBlank; onDone: () => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const [label, setLabel] = useState("");
  const [required, setRequired] = useState(true);
  const [fallback, setFallback] = useState("");
  const { busy, error, send } = useSend(onDone);
  const id = `tpl-blank-${where}-${blank.n}`;
  return (
    <li>
      <span className="tpl-pubrow__what">&hellip;{blank.before} <mark className="tpl-blank">blank {blank.n}</mark> {blank.after}&hellip;</span>
      {blank.field ? (
        <span className="tpl-pubrow__said">Sales fills &ldquo;{blank.field.label}&rdquo; on each deal.
          {blank.field.required ? " Required to create the contract."
            : blank.field.default ? ` If sales leaves it empty: “${blank.field.default}”.`
              : " Can stay empty for now, but the final contract is blocked until it is filled."}</span>
      ) : !open ? (
        <span className="tpl-pubrow__where">
          <span>Not a field yet. Left as is, this blank stops the final contract.</span>
          <button type="button" className="tpl-link" onClick={() => setOpen(true)}>Make a fill-in field</button></span>
      ) : (
        <form className="tpl-form" onSubmit={(e) => {
          e.preventDefault();
          if (label.trim() && (required || fallback.trim())) {
            void send(() => api.makeBlankField(templateId, { where, n: blank.n, label: label.trim(), required,
                                                             ...(required ? {} : { default: fallback.trim() }) }));
          }
        }}>
          <label htmlFor={id} className="tpl-label">What sales is asked</label>
          <input id={id} className="tpl-reason" type="text" maxLength={120} required value={label}
                 aria-describedby={`${id}-help`} onChange={(e) => setLabel(e.target.value)} />
          <p id={`${id}-help`} className="tpl-help">For example &ldquo;City where banks are open&rdquo;. The approved words do not change.</p>
          <label className="tpl-check"><input type="checkbox" checked={required} onChange={(e) => setRequired(e.target.checked)} />
            Required to create the contract</label>
          {required ? null : (<>
            <label htmlFor={`${id}-default`} className="tpl-label">Value if sales leaves it empty</label>
            <input id={`${id}-default`} className="tpl-reason" type="text" maxLength={300} required value={fallback}
                   aria-describedby={`${id}-default-help`} onChange={(e) => setFallback(e.target.value)} />
            <p id={`${id}-default-help`} className="tpl-help">Type the words exactly as the contract should read. A blank never goes to the client as underscores.</p>
          </>)}
          {error ? <p className="tpl-error" role="alert">{error}</p> : null}
          <div className="tpl-actions__row">
            <button type="button" className="ws-btn" onClick={() => setOpen(false)}>Cancel</button>
            <button type="submit" className="ws-btn" disabled={busy || !label.trim() || (!required && !fallback.trim())}>{busy ? "Saving…" : "Make field"}</button>
          </div>
        </form>
      )}
    </li>
  );
}

/** Every underscore blank in the approved words, and what happens to it on a deal (`AM-392`). */
export function BlanksGroup({ detail, onDone }: { detail: TemplateDetail; onDone: () => Promise<void> }) {
  const places: { where: string; title: string; blanks: TemplateBlank[] }[] = [
    { where: "preamble", title: "Opening paragraph", blanks: detail.front_blanks?.preamble ?? [] },
    { where: "recitals", title: "Recitals", blanks: detail.front_blanks?.recitals ?? [] },
    ...detail.clauses.map((c) => ({ where: c.clause_key, title: displayTitle(c.title), blanks: c.blanks ?? [] })),
  ].filter((p) => p.blanks.length);
  if (!places.length) return null;
  const count = places.reduce((n, p) => n + p.blanks.length, 0);
  return (
    <div className="tpl-pubgroup"><h3>Blanks in the approved words <span>{count}</span></h3>
      <p className="tpl-help">A blank never reaches a final contract as underscores. Make each one a fill-in field that
        sales completes on the deal. A blank left empty stops the final contract until it is filled.</p>
      {places.map((p) => (
        <div key={p.where}><h4 className="tpl-label">{p.title}</h4>
          <ul>{p.blanks.map((b) => <BlankRow key={b.n} templateId={detail.id} where={p.where} blank={b} onDone={onDone} />)}</ul>
        </div>
      ))}
    </div>
  );
}


/** U1 (`AM-307`): whether agreed changes to a contract made from this template can go out
 *  as Special Conditions (Annexure A) — the server's readiness, in words. It never stops
 *  publishing; without it a deal goes back as a reply with tracked changes. */
export function SpecialConditionsSetup({ readiness }: { readiness?: SpecialConditionsReadiness | undefined }) {
  if (!readiness) return null;
  return (
    <div className="tpl-pubgroup" data-sc={readiness.ready ? "ready" : "not-set-up"}>
      <h3>Special Conditions (Annexure A)</h3>
      {readiness.ready ? (
        <p className="tpl-help"><strong>Set up.</strong> When a client&rsquo;s changes are agreed, a contract made from
          this template goes out as a final contract: this text unchanged, with each agreed change in Annexure A, and a
          clause saying Annexure A wins.</p>
      ) : (
        <>
          {readiness.missing.some((m) => m.code === "NOT_CONFIGURED") ? (
            <p className="tpl-help"><strong>Not set up.</strong> Agreed changes go back to the client as tracked changes
              instead of a final contract. It does not stop publishing. An administrator sets it up when the template is
              imported; it cannot be set up from this page yet.</p>
          ) : (
            // prelaunch U5: attached but incomplete — never "Not set up", and say what it blocks
            <p className="tpl-help"><strong>Not complete.</strong> Publishing is allowed, but no final contract can be
              made from this template until the item below is done.</p>
          )}
          {readiness.missing.some((m) => m.code !== "NOT_CONFIGURED") ? (
            <ul>{readiness.missing.map((m) => (
              <li key={m.code}><span className="tpl-pubrow__what">{blockerText({ code: `SC_${m.code}`, detail: m.detail })}</span></li>
            ))}</ul>
          ) : null}
        </>
      )}
    </div>
  );
}
