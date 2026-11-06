"use client";

/**
 * Record signing — the closing step of a deal (CLM flow 5 "Final", `AM-292`).
 *
 * One sheet, three sections in the order they happen — Stamp duty · Who signed · Signed
 * copy — and one final act, "Mark signed". Presentation only (rule 18): what still stops
 * signing is the server's `blockers`, the comparison of the signed copy with the agreed
 * version is the server's, and every write is checked again there. LegalMind records what
 * was done; it never works out a duty, an article or a rate (rules 7, 21).
 */

import { useCallback, useEffect, useId, useState } from "react";

import { Dialog } from "@/components/Dialog";
import { api, describeError } from "@/lib/api";
import {
  AUTHORITY_KINDS, KIND_LABEL, PARTY_LABEL, SIGN_METHODS, STAMP_METHODS,
  cleaned, partyRows, signatoriesRecorded, signingView, stampRecorded, toFields,
  type ExecutionFields, type ExecutionState, type SignedComparison, type Signatory,
} from "@/lib/execution";
import { useStep } from "@/lib/nextStep";
import type { DocumentVersion } from "@/lib/types";

import { IconCheck } from "./icons";
import { shortDate } from "./model";
import "./signing.css";

export function RecordSigning({ contractId, label, primary = false, onSigned, versions }: {
  contractId: string; label: string; primary?: boolean; onSigned: () => void;
  /** the contract's versions — to say when the agreed one is a final contract (`AM-307`) */
  versions?: DocumentVersion[] | undefined;
}) {
  const [open, setOpen] = useState(false);
  useStep("recordSigning", useCallback(() => setOpen(true), []));
  return (
    <>
      <button type="button" className={`ws-btn ws-btn--sm${primary ? " ws-btn--primary" : ""}`}
              onClick={() => setOpen(true)}>
        {label}
      </button>
      {open ? <SigningSheet contractId={contractId} onClose={() => setOpen(false)} onSigned={onSigned}
                           versions={versions} /> : null}
    </>
  );
}

function SigningSheet({ contractId, onClose, onSigned, versions }: {
  contractId: string; onClose: () => void; onSigned: () => void; versions?: DocumentVersion[] | undefined;
}) {
  const titleId = useId();
  const [state, setState] = useState<ExecutionState | null>(null);
  const [fields, setFields] = useState<ExecutionFields>({});
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState<null | "save" | "sign" | "upload" | "accept">(null);
  const [error, setError] = useState<string | null>(null);

  const take = useCallback((next: ExecutionState) => {
    setState(next);
    setFields(toFields(next));
    setDirty(false);
  }, []);
  const load = useCallback(() => {
    api.execution(contractId).then(take).catch((cause) => setError(describeError(cause)));
  }, [contractId, take]);
  useEffect(load, [load]);

  const edit = (patch: ExecutionFields) => { setFields((f) => ({ ...f, ...patch })); setDirty(true); };
  const editPerson = (party: Signatory["party"], patch: Partial<Signatory>) =>
    edit({ signatories: partyRows(fields.signatories).map((s) => (s.party === party ? { ...s, ...patch } : s)) });

  const save = async (extra: ExecutionFields = {}): Promise<ExecutionState | null> => {
    const next = await api.saveExecution(contractId, cleaned({ ...fields, ...extra }),
                                         state?.execution ? state.execution.version : null);
    take(next);
    return next;
  };
  const run = async (kind: NonNullable<typeof busy>, act: () => Promise<unknown>) => {
    setBusy(kind);
    setError(null);
    try { await act(); } catch (cause) { setError(describeError(cause)); } finally { setBusy(null); }
  };

  const upload = (file: File) => run("upload", async () => {
    const { document_version } = await api.uploadDocument(contractId, file);
    await save({ signed_document_version_id: document_version.id });
  });
  const markSigned = () => run("sign", async () => {
    const saved = dirty ? await save() : state;
    if (!saved?.execution || saved.blockers.length || !saved.execution.signed_document_version_id) return;
    take(await api.markSigned(contractId, saved.execution.signed_document_version_id, saved.execution.version));
    onSigned();
  });

  const view = state ? signingView(state) : null;
  const signed = !!view && view !== "form";
  return (
    <Dialog onClose={onClose} titleId={titleId} dismissOnScrimClick={!dirty} overlayClassName="lm-sign">
      <header className="lm-sign__head">
        <h2 id={titleId}>{signed ? "Signing record" : "Record signing"}</h2>
        <button type="button" className="ws-btn ws-btn--sm" onClick={onClose}>Close</button>
      </header>
      {!state ? (
        error ? <p className="cx-error" role="alert">{error}</p> : <p className="ws-pane__note">Loading…</p>
      ) : view === "legacy" ? (
        <div className="lm-sign__body">
          <p className="lm-sign__signed"><IconCheck size={16} aria-hidden /> Signed outside LegalMind (no signing record)</p>
        </div>
      ) : view === "filed" ? (
        <>
          <div className="lm-sign__body">
            <p className="ws-pane__note">
              Filed as signed outside LegalMind. Stamp duty and who signed are optional. Confirming makes this record final.
            </p>
            <StampSection fields={fields} edit={edit} />
            <PeopleSection fields={fields} edit={edit} editPerson={editPerson} />
          </div>
          <footer className="lm-sign__foot">
            {dirty ? <p className="lm-sign__todo">You have changes that are not saved yet.</p> : null}
            {error ? <p className="cx-error" role="alert">{error}</p> : null}
            <div className="lm-sign__acts">
              <button type="button" className="ws-btn ws-btn--sm" disabled={!dirty || !!busy}
                      onClick={() => void run("save", () => save())}>
                {busy === "save" ? "Saving…" : "Save"}
              </button>
              <button type="button" className="ws-btn ws-btn--sm ws-btn--primary"
                      disabled={!!busy} onClick={() => void markSigned()}>
                {busy === "sign" ? "Confirming…" : "Confirm the record"}
              </button>
            </div>
          </footer>
        </>
      ) : view === "summary" ? (
        <SignedSummary state={state} />
      ) : (
        <>
          <div className="lm-sign__body">
            <StampSection fields={fields} edit={edit} />
            <PeopleSection fields={fields} edit={edit} editPerson={editPerson} />
            <CopySection state={state} busy={busy} onUpload={(f) => void upload(f)} onRefresh={load}
              annexure={versions?.find((v) => v.id === state.agreed?.document_version_id)?.package?.special_conditions}
              onAccept={(reason) => void run("accept", async () => {
                if (dirty) await save();
                const version = state.execution?.version;
                if (version) take(await api.acceptSignedDifferences(contractId, version, reason));
              })} />
          </div>
          <footer className="lm-sign__foot">
            {dirty ? (
              <p className="lm-sign__todo">You have changes that are not saved yet.</p>
            ) : state.blockers.length ? (
              <div className="lm-sign__todo">
                <p>Before it can be marked signed:</p>
                <ul>{state.blockers.map((b) => <li key={b.code}>{b.message}</li>)}</ul>
              </div>
            ) : (
              <p className="lm-sign__todo lm-sign__todo--ok">
                <IconCheck size={14} aria-hidden /> Everything is recorded. Marking it signed makes this record final.
              </p>
            )}
            {error ? <p className="cx-error" role="alert">{error}</p> : null}
            <div className="lm-sign__acts">
              <button type="button" className="ws-btn ws-btn--sm" disabled={!dirty || !!busy}
                      onClick={() => void run("save", () => save())}>
                {busy === "save" ? "Saving…" : "Save"}
              </button>
              <button type="button" className="ws-btn ws-btn--sm ws-btn--primary"
                      disabled={!!busy || (!dirty && state.blockers.length > 0)} onClick={() => void markSigned()}>
                {busy === "sign" ? "Marking signed…" : "Mark signed"}
              </button>
            </div>
          </footer>
        </>
      )}
    </Dialog>
  );
}

function Section({ title, done, children }: { title: string; done: boolean; children: React.ReactNode }) {
  return (
    <section className="lm-sign__sec" aria-label={title}>
      <div className="lm-sign__sechead">
        <h3>{title}</h3>
        <span className={`lm-sign__mark${done ? " lm-sign__mark--done" : ""}`}>
          {done ? <><IconCheck size={13} aria-hidden /> Recorded</> : "Needed"}
        </span>
      </div>
      {children}
    </section>
  );
}

function Field({ label, help, children }: { label: string; help?: string; children: React.ReactNode }) {
  return (
    <label className="ws-field">
      <span className="ws-field__label">{label}</span>
      {children}
      {help ? <span className="ws-field__help">{help}</span> : null}
    </label>
  );
}

function StampSection({ fields, edit }: { fields: ExecutionFields; edit: (p: ExecutionFields) => void }) {
  const method = fields.stamp_method ?? null;
  return (
    <Section title="Stamp duty" done={stampRecorded(fields)}>
      <p className="lm-sign__why">
        An unstamped contract is still valid, but a court will not accept it as evidence until the
        stamp duty and any penalty are paid. Stamping is done before or when the contract is signed.
        Record what was done here; LegalMind does not work out the duty — ask Legal if you are unsure.
      </p>
      <fieldset className="lm-sign__choice">
        <legend className="ws-field__label">How was it stamped?</legend>
        {STAMP_METHODS.map((m) => (
          <label key={m.value} className={`lm-sign__opt${method === m.value ? " lm-sign__opt--on" : ""}`}>
            <input type="radio" name="stamp_method" value={m.value} checked={method === m.value}
                   onChange={() => edit({ stamp_method: m.value })} />
            <span><strong>{m.label}</strong><small>{m.hint}</small></span>
          </label>
        ))}
      </fieldset>
      {method === "NOT_STAMPED" ? (
        <label className="lm-sign__ack">
          <input type="checkbox" checked={!!fields.not_stamped_acknowledged}
                 onChange={(e) => edit({ not_stamped_acknowledged: e.target.checked })} />
          <span>I understand this contract cannot be used as evidence until it is stamped and any penalty is paid.</span>
        </label>
      ) : method ? (
        <div className="lm-sign__grid">
          <Field label={method === "E_STAMP" ? "Certificate number" : "Stamp paper number"}
                 help={method === "E_STAMP" ? "As printed on the e-stamp certificate." : "Every sheet, if there are several."}>
            <input value={fields.stamp_reference ?? ""} onChange={(e) => edit({ stamp_reference: e.target.value })} />
          </Field>
          <Field label="State">
            <input value={fields.stamp_state ?? ""} onChange={(e) => edit({ stamp_state: e.target.value })} />
          </Field>
          <Field label="Duty paid (₹)" help="As shown on the certificate or paper.">
            <input value={fields.duty_paid ?? ""} onChange={(e) => edit({ duty_paid: e.target.value })} />
          </Field>
          <Field label="Stamped on">
            <input type="date" value={fields.stamped_on ?? ""} onChange={(e) => edit({ stamped_on: e.target.value })} />
          </Field>
        </div>
      ) : null}
    </Section>
  );
}

function PeopleSection({ fields, edit, editPerson }: {
  fields: ExecutionFields; edit: (p: ExecutionFields) => void;
  editPerson: (party: Signatory["party"], patch: Partial<Signatory>) => void;
}) {
  const witnesses = fields.witnesses ?? [];
  return (
    <Section title="Who signed" done={signatoriesRecorded(fields.signatories)}>
      <p className="lm-sign__why">
        For a company, the person signing needs its authority — usually a board resolution or an
        authority letter. Record which one, and its date.
      </p>
      {partyRows(fields.signatories).map((s) => (
        <fieldset key={s.party} className="lm-sign__party">
          <legend>{PARTY_LABEL[s.party]}</legend>
          <div className="lm-sign__grid">
            <Field label="Name"><input value={s.name ?? ""} onChange={(e) => editPerson(s.party, { name: e.target.value })} /></Field>
            <Field label="Designation"><input value={s.designation ?? ""} onChange={(e) => editPerson(s.party, { designation: e.target.value })} /></Field>
            <Field label="Authority">
              <select value={s.authority_kind ?? ""} onChange={(e) => editPerson(s.party, {
                authority_kind: (e.target.value || null) as "BOARD_RESOLUTION" | null })}>
                <option value="">Choose…</option>
                {AUTHORITY_KINDS.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}
              </select>
            </Field>
            <Field label="Its reference" help="The resolution or letter number, as written on it.">
              <input value={s.authority_reference ?? ""} onChange={(e) => editPerson(s.party, { authority_reference: e.target.value })} />
            </Field>
            <Field label="Dated">
              <input type="date" value={s.authority_date ?? ""} onChange={(e) => editPerson(s.party, { authority_date: e.target.value })} />
            </Field>
            <Field label="Signed on">
              <input type="date" value={s.signed_on ?? ""} onChange={(e) => editPerson(s.party, { signed_on: e.target.value })} />
            </Field>
            <Field label="How it was signed">
              <select value={s.method ?? ""} onChange={(e) => editPerson(s.party, {
                method: (e.target.value || null) as "WET_INK" | null })}>
                <option value="">Choose…</option>
                {SIGN_METHODS.map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}
              </select>
            </Field>
          </div>
        </fieldset>
      ))}
      <details className="lm-sign__more">
        <summary>Seal and witnesses (optional)</summary>
        <label className="lm-sign__ack">
          <input type="checkbox" checked={!!fields.seal_used} onChange={(e) => edit({ seal_used: e.target.checked })} />
          <span>A company seal was used</span>
        </label>
        <div className="lm-sign__grid">
          {[0, 1].map((i) => (
            <Field key={i} label={`Witness ${i + 1}`}>
              <input value={witnesses[i] ?? ""} onChange={(e) => {
                const next = [witnesses[0] ?? "", witnesses[1] ?? ""];
                next[i] = e.target.value;
                edit({ witnesses: next });
              }} />
            </Field>
          ))}
        </div>
      </details>
    </Section>
  );
}

export function CopySection({ state, busy, onUpload, onRefresh, onAccept, annexure }: {
  state: ExecutionState; busy: string | null; onUpload: (file: File) => void; onRefresh: () => void;
  onAccept: (reason: string) => void;
  /** the agreed version is a final contract with this many Special Conditions */
  annexure?: number | undefined;
}) {
  const inputId = useId();
  const [reason, setReason] = useState("");
  const c = state.comparison;
  const accepted = !!state.execution?.differences_accepted;
  const agreed = state.agreed ? `version ${state.agreed.version_number}` : "the agreed version";
  return (
    <Section title="Signed copy" done={c?.status === "MATCHES" || (!!c && accepted)}>
      <p className="lm-sign__why">
        {annexure !== undefined ? (
          <>Upload the copy both sides signed, including Annexure A with
            its {annexure === 1 ? "1 Special Condition" : `${annexure} Special Conditions`}. It is compared
            with {agreed}, the final contract, before the contract is marked signed.</>
        ) : (
          <>Upload the copy both sides signed. It is compared with {agreed} — the text you agreed —
            before the contract is marked signed.</>
        )}
      </p>
      <div className="lm-sign__upload">
        <label htmlFor={inputId} className="ws-btn ws-btn--sm">
          {busy === "upload" ? "Uploading…" : c ? "Upload a different copy" : "Upload the signed copy"}
        </label>
        <input id={inputId} type="file" className="lm-sign__file" accept=".pdf,.docx" disabled={!!busy}
               onChange={(e) => { const f = e.target.files?.[0]; if (f) onUpload(f); e.target.value = ""; }} />
        {c ? <span className="ws-pane__note">Version {c.signed.version_number}</span> : null}
      </div>
      {c ? <Verdict c={c} agreed={agreed} accepted={accepted} reason={state.execution?.differences_reason ?? null} /> : null}
      {c?.status === "NOT_COMPARED" ? (
        <button type="button" className="ws-linkbtn" onClick={onRefresh}>Check again</button>
      ) : null}
      {c && c.status !== "MATCHES" && !accepted ? (
        state.can_accept_differences ? (
          <div className="lm-sign__accept">
            <Field label="Accept these differences" help="Say why the signed copy may stand as it is. Recorded with your name.">
              <textarea rows={2} value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} />
            </Field>
            <button type="button" className="ws-btn ws-btn--sm" disabled={!reason.trim() || !!busy}
                    onClick={() => onAccept(reason.trim())}>
              {busy === "accept" ? "Accepting…" : "Accept differences"}
            </button>
          </div>
        ) : (
          <p className="ws-pane__note">Upload the right copy, or ask Legal to accept the differences.</p>
        )
      ) : null}
    </Section>
  );
}

function Verdict({ c, agreed, accepted, reason }: {
  c: SignedComparison; agreed: string; accepted: boolean; reason: string | null;
}) {
  if (c.status === "MATCHES") {
    return <p className="lm-sign__verdict lm-sign__verdict--ok"><IconCheck size={14} aria-hidden /> Signed copy matches the agreed version ({agreed}).</p>;
  }
  if (c.status === "NOT_COMPARED") {
    return <p className="lm-sign__verdict lm-sign__verdict--warn">Not compared yet: {c.reason}</p>;
  }
  const n = c.differences.length;
  return (
    <div className={`lm-sign__verdict lm-sign__verdict--${accepted ? "ok" : "warn"}`}>
      <p>
        {accepted ? "Differences accepted by Legal" : `The signed copy differs from ${agreed} in ${n} place${n === 1 ? "" : "s"}`}
        {accepted && reason ? `: ${reason}` : "."}
      </p>
      <ol className="lm-sign__diffs">
        {c.differences.map((d, i) => (
          <li key={i}>
            <span className="lm-sign__where">
              {d.clause.number ? `Clause ${d.clause.number}` : d.clause.heading || (d.page ? `Page ${d.page}` : "A clause")}
              <small>{KIND_LABEL[d.kind]}</small>
            </span>
            {d.agreed_text && d.kind !== "MOVED" ? <del>{clip(d.agreed_text, firstDifference(d))}</del> : null}
            {d.signed_text ? <ins>{clip(d.signed_text, firstDifference(d))}</ins> : null}
          </li>
        ))}
      </ol>
    </div>
  );
}

/** Where the two texts first part — so a long clause shows the words that changed. */
export function firstDifference(d: { agreed_text?: string | null; signed_text?: string | null }): number {
  const a = d.agreed_text ?? "", b = d.signed_text ?? "";
  let i = 0;
  while (i < a.length && i < b.length && a[i] === b[i]) i += 1;
  return i;
}

/** About 280 characters around ``at``, marked with … where cut. */
export function clip(text: string, at = 0): string {
  const start = Math.max(0, Math.min(at - 100, text.length - 280));
  const end = Math.min(text.length, start + 280);
  return `${start > 0 ? "…" : ""}${text.slice(start, end)}${end < text.length ? "…" : ""}`;
}

const NONE = "Not recorded";

/** The signatory's authority as one phrase: "Board resolution BR/2026/14 of 1 Oct 2026". A
 *  reference that already names its kind or date (a client profile's "Board resolution of
 *  1 Oct 2026") is not given them twice. Empty when nothing is recorded. */
export function authorityWords(s: Pick<Signatory, "authority_kind" | "authority_reference" | "authority_date">): string {
  const label = AUTHORITY_KINDS.find((k) => k.value === s.authority_kind)?.label ?? "";
  const ref = (s.authority_reference ?? "").trim();
  const date = s.authority_date ? shortDate(s.authority_date) : "";
  const said = (part: string) => !!part && ref.toLowerCase().includes(part.toLowerCase());
  return [said(label) ? "" : label, ref, date && !said(date) ? `of ${date}` : ""]
    .filter(Boolean).join(" ");
}

/** "Signed on paper on 2 Nov 2026", "E-signed", "Signed on 2 Nov 2026" — or empty. */
export function signedWords(s: Pick<Signatory, "method" | "signed_on">): string {
  const how = SIGN_METHODS.find((m) => m.value === s.method)?.label;
  const on = s.signed_on ? `on ${shortDate(s.signed_on)}` : "";
  return how ? [how, on].filter(Boolean).join(" ") : on ? `Signed ${on}` : "";
}

function SignedSummary({ state }: { state: ExecutionState }) {
  const r = state.execution!;
  const method = STAMP_METHODS.find((m) => m.value === r.stamp_method)?.label ?? NONE;
  const copy = r.signed_document_version_id;
  return (
    <div className="lm-sign__body">
      <p className="lm-sign__signed">
        <IconCheck size={16} aria-hidden />{" "}
        {r.origin === "SIGNED_OUTSIDE" ? "Signed outside LegalMind" : `Signed on ${shortDate(r.signed_at)}`}
      </p>
      <Section title="Stamp duty" done>
        <dl className="lm-sign__dl">
          <dt>How</dt><dd>{method}</dd>
          {r.stamp_method === "NOT_STAMPED" ? (
            <><dt>Note</dt><dd>Not stamped — it cannot be used as evidence until it is stamped.</dd></>
          ) : (
            <>
              <dt>Reference</dt><dd>{r.stamp_reference ?? NONE}</dd>
              <dt>State</dt><dd>{r.stamp_state ?? NONE}</dd>
              {/* stored as typed (no duty is computed); a bare amount is said in rupees */}
              <dt>Duty paid</dt><dd>{r.duty_paid ? (/^\d[\d,]*(\.\d+)?$/.test(r.duty_paid.trim()) ? `₹${r.duty_paid.trim()}` : r.duty_paid) : NONE}</dd>
              {r.stamped_on ? <><dt>Stamped on</dt><dd>{shortDate(r.stamped_on)}</dd></> : null}
            </>
          )}
        </dl>
      </Section>
      <Section title="Who signed" done>
        <dl className="lm-sign__dl">
          {partyRows(r.signatories).map((s) => (
            <div key={s.party} className="lm-sign__dlrow">
              <dt>{PARTY_LABEL[s.party]}</dt>
              <dd>
                {[s.name, s.designation].filter(Boolean).join(", ") || NONE}
                {authorityWords(s) ? <small>{authorityWords(s)}</small> : null}
                {signedWords(s) ? <small>{signedWords(s)}</small> : null}
              </dd>
            </div>
          ))}
          {r.seal_used ? <><dt>Seal</dt><dd>Company seal used</dd></> : null}
          {r.witnesses.length ? <><dt>Witnesses</dt><dd>{r.witnesses.join(", ")}</dd></> : null}
        </dl>
      </Section>
      <Section title="Signed copy" done>
        {state.comparison ? (
          <p className="ws-pane__note">
            {state.comparison.status === "MATCHES"
              ? `Matched the agreed version (version ${state.comparison.agreed.version_number}).`
              : `Differed from the agreed version; accepted by Legal${r.differences_reason ? `: ${r.differences_reason}` : "."}`}
          </p>
        ) : null}
        {copy ? (
          <a className="ws-btn ws-btn--sm" href={api.documentContentUrl(copy)} download>Download the signed copy</a>
        ) : null}
      </Section>
    </div>
  );
}
