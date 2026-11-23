"use client";

/**
 * Client details (batch 7, AB-220) — Legal's items for an MSA, entered ONCE on the client
 * record, certificate first. Every field saves itself to the client on leaving it (one
 * record, no Save button); a value read from the certificate is shown as read until a person
 * confirms it, edits it, or ticks "checked" (the server confirms it then). Every status,
 * check and the edit right are the server's (rule 18); this card only presents them.
 */

import { useEffect, useState } from "react";

import { api, ApiError, describeError } from "@/lib/api";
import {
  CARD_GROUPS, EMAIL_FIELDS, GST_PORTAL, MCA_MASTER_DATA, groupDone, itemOf,
  type ChecklistItem, type ClientChecklist, type ReadValue,
} from "@/lib/clientDetails";
import { countryChoices } from "@/lib/countries";
import { formatDate } from "@/lib/dates";
import { INTAKE_COPY as C } from "@/lib/labels";
import type { Counterparty } from "@/lib/types";
import { FilePicker } from "@/components/FilePicker";
import { toast, toastFailure } from "@/components/Toast";
import {
  IconCheckCircle, IconCircle, IconCopy, IconExternal, IconFilePlus, IconNotNeeded, IconScanText, IconTriangleAlert,
} from "@/components/workspace/icons";

type Rec = Record<string, unknown>;
const textOf = (c: Counterparty, f: string) => String((c as unknown as Rec)[f] ?? "");

/** One checklist state, as words + icon (never a point status's words or hues). */
export function ItemState({ item, refused }: { item: ChecklistItem | undefined; refused: boolean }) {
  if (!item) return null;
  const tone = item.status === "missing" && refused ? "refused" : item.status;
  const Icon = { done: IconCheckCircle, missing: IconCircle, not_needed: IconNotNeeded, fix: IconTriangleAlert,
    refused: IconFilePlus }[tone];
  return <span className="ic-state" data-tone={tone}><Icon size={14} />{C.status[tone]}</span>;
}

/** Benchmark 2: a small tick beside a card group's heading once the server says it is complete. */
function Done({ ok }: { ok: boolean }) {
  return ok ? <span className="ic-group__done"><IconCheckCircle size={16} /><span className="ws-visually-hidden">{C.groupDone}</span></span> : null;
}

function Copy({ label, value }: { label: string; value: string }) {
  return (
    <button type="button" className="ic-icon" aria-label={C.copy(label)} title={C.copy(label)}
            onClick={() => void navigator.clipboard.writeText(value).then(() => toast(C.copied), toastFailure(C.copy(label)))}>
      <IconCopy size={16} />
    </button>
  );
}

export function ClientDetailsCard({ client, checklist, refused, onClient }: {
  client: Counterparty;
  checklist: ClientChecklist;
  /** Create was refused: what is still unfilled says so in orange */
  refused: boolean;
  /** the client record as the server returned it after a change */
  onClient: (c: Counterparty) => void;
}) {
  const reads = new Map((checklist.reads ?? []).map((r) => [r.field, r]));
  const drafted = checklist.draft_values ?? {};
  const shown = (f: string) => textOf(client, f) || (reads.get(f)?.state === "fill" ? reads.get(f)!.value : "")
    || drafted[f] || "";
  const [local, setLocal] = useState<Record<string, string>>({});
  const [touched, setTouched] = useState<Set<string>>(new Set());
  const [state, setState] = useState<Record<string, "saving" | "saved" | "error">>({});
  const [editing, setEditing] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [justRead, setJustRead] = useState<number | null>(null);
  const [ticking, setTicking] = useState(false);
  const [tickError, setTickError] = useState<string | null>(null);

  const dirty = [...touched].some((f) => (local[f] ?? "").trim() !== textOf(client, f));
  useEffect(() => {          // review change 8: leaving with a field typed and not yet saved
    if (!dirty) return;
    const stop = (e: BeforeUnloadEvent) => { e.preventDefault(); };
    window.addEventListener("beforeunload", stop);
    return () => window.removeEventListener("beforeunload", stop);
  }, [dirty]);

  async function save(patch: Record<string, string | null>, fields: string[]) {
    setState((s) => ({ ...s, ...Object.fromEntries(fields.map((f) => [f, "saving"])) }));
    try {
      onClient(await api.updateCounterparty(client.id, patch));
      setTouched((t) => new Set([...t].filter((f) => !fields.includes(f))));
      setState((s) => ({ ...s, ...Object.fromEntries(fields.map((f) => [f, "saved"])) }));
    } catch (e) {
      const bad = e instanceof ApiError && e.fields?.length ? e.fields.map((x) => x.field) : fields;
      setState((s) => ({ ...s, ...Object.fromEntries(bad.map((f) => [f, "error"])) }));
    }
  }
  const confirmReads = (rs: ReadValue[]) =>
    void save(Object.fromEntries(rs.map((r) => [r.field, r.value])), rs.map((r) => r.field));

  async function upload(file: File | null) {
    if (!file) return;
    setUploading(true); setUploadError(null);
    try {
      const c = await api.uploadGstCertificate(client.id, file);
      // the fields a person checks (the PAN and state are derived from the GST number)
      setJustRead(CARD_GROUPS[0].fields.filter((f) => c.gst_certificate?.read?.[f]).length);
      onClient(c);
    } catch (e) { setUploadError(describeError(e)); } finally { setUploading(false); }
  }

  async function tick() {
    setTicking(true); setTickError(null);
    try { onClient(await api.verifyClientDetails(client.id)); } catch (e) { setTickError(describeError(e)); }
    finally { setTicking(false); }
  }

  const name = client.name;
  const rec = client as unknown as Rec;
  const cert = client.gst_certificate;
  const certItem = itemOf(checklist, "gst_certificate");
  const unconfirmed = [...reads.values()].filter((r) => r.state === "fill");
  const shownUnconfirmed = unconfirmed.filter((r) => r.field !== "pan");
  const canEdit = checklist.can_edit !== false;
  const tickReady = !!checklist.tick_ready;
  const india = checklist.india !== false;

  if (checklist.client_ready && !editing) {
    return (
      <section className="ic-card ic-card--onfile" aria-labelledby="ic-card-t">
        <IconCheckCircle size={20} />
        <div>
          <h2 id="ic-card-t" className="ic-card__h">{C.onFile}</h2>
          {checklist.verified ? <p className="ic-quiet">{C.checkedBy(checklist.verified.by ?? "", formatDate(checklist.verified.at))}</p> : null}
        </div>
        {canEdit ? <button type="button" className="ws-btn ws-btn--sm" onClick={() => setEditing(true)}>{C.edit}</button> : null}
      </section>
    );
  }

  function field(f: string) {
    const id = `ic-f-${f}`;
    const words = C.fields[f]!;
    const item = itemOf(checklist, f);
    const read = reads.get(f);
    const value = touched.has(f) ? (local[f] ?? "") : shown(f);
    const marked = read?.state === "fill" && !touched.has(f);
    // D8: an older draft's typed answer where the record is empty — offered, never saved unasked
    const fromDraft = !marked && !touched.has(f) && !textOf(client, f) && !!drafted[f];
    const err = state[f] === "error" ? (item?.problem ? C.problems[item.problem] : C.saveFailed)
      : item?.status === "fix" && item.problem ? C.problems[item.problem] : null;
    const warn = checklist.warnings.filter((w) =>
      (f === "registered_office" && (w.code === "state_differs" || w.code === "state_unreadable"))
      || (f === "cin_or_llpin" && w.code === "act_wording") || (f === "legal_name" && w.code === "name_differs"));
    const describedBy = [item?.status === "not_needed" ? "" : `${id}-help`, marked ? `${id}-read` : "", fromDraft ? `${id}-draft` : "", err ? `${id}-err` : "", warn.length ? `${id}-warn` : ""]
      .filter(Boolean).join(" ");
    const notNeeded = item?.status === "not_needed";
    return (
      <div key={f} className="ic-field" data-wide={f === "registered_office" || undefined}>
        <div className="ic-field__head">
          <label htmlFor={id} className="ic-field__label">{words.label}</label>
          {/* a field still empty is bare (the panel says what is left); a read value shows its marker */}
          {!marked && !fromDraft && (item?.status !== "missing" || refused) ? <ItemState item={item} refused={refused} /> : null}
        </div>
        {notNeeded ? null : (
          <p id={`${id}-help`} className="ic-field__help">
            {f === "country" && !checklist.country_abroad ? C.countryIndia
              : !india && words.help === C.fields.registered_email!.help ? C.asRegistered : words.help}</p>
        )}
        {notNeeded ? null : canEdit ? (
          <div className="ic-field__row">
            {f === "country" ? (
              // D2: a choice list; the server reads it (India rules unless clearly another country)
              <select id={id} value={value} aria-describedby={describedBy}
                      onChange={(e) => { setLocal((l) => ({ ...l, [f]: e.target.value })); setTouched((t) => new Set(t).add(f)); void save({ [f]: e.target.value || null }, [f]); }}>
                <option value="">{C.countryChoose}</option>
                {countryChoices(value).map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            ) : f === "registered_office"
              ? <textarea id={id} rows={2} value={value} aria-describedby={describedBy} aria-invalid={err ? true : undefined}
                          onChange={(e) => { setLocal((l) => ({ ...l, [f]: e.target.value })); setTouched((t) => new Set(t).add(f)); }}
                          onBlur={() => blur(f)} />
              : <input id={id} type={EMAIL_FIELDS.has(f) ? "email" : "text"} value={value} aria-describedby={describedBy}
                       aria-invalid={err ? true : undefined} autoComplete="off"
                       onChange={(e) => { setLocal((l) => ({ ...l, [f]: e.target.value })); setTouched((t) => new Set(t).add(f)); }}
                       onBlur={() => blur(f)} />}
            {(f === "gstin" || f === "cin_or_llpin") && value ? <Copy label={words.label} value={value} /> : null}
          </div>
        ) : <p className="ic-field__value">{value || C.status.missing}</p>}
        {marked ? (
          <p id={`${id}-read`} className="ic-read"><IconScanText size={14} />{C.marker}</p>
        ) : null}
        {fromDraft ? (
          <p id={`${id}-draft`} className="ic-read"><IconScanText size={14} />{C.fromDraft}
            {canEdit ? <button type="button" className="nc-linkbtn" onClick={() => void save({ [f]: drafted[f]! }, [f])}>{C.confirm}</button> : null}</p>
        ) : null}
        {f === "gstin" && !notNeeded && cert?.read?.gstin_unreadable && !textOf(client, f) ? <p className="ic-field__err">{C.gstinUnreadable}</p> : null}
        {/* benchmark 4: an accepted read keeps saying where it came from */}
        {read?.state === "same" && !touched.has(f) ? <p className="ic-read ic-read--done"><IconScanText size={14} />{C.fromCertificate}</p> : null}
        {read?.state === "differs" && canEdit ? (
          <p className="ic-read"><IconScanText size={14} />{C.differs(read.value)}
            <button type="button" className="nc-linkbtn" onClick={() => confirmReads([read])}>{C.useThis}</button></p>
        ) : null}
        {f === "gstin" && (client.pan || reads.get("pan")) ? (
          <p className="ic-field__help">{C.derived(client.pan ?? reads.get("pan")!.value, cert?.read?.state)}</p>
        ) : null}
        {err ? <p id={`${id}-err`} className="ic-field__err">{err}</p> : null}
        {warn.length ? (
          <div id={`${id}-warn`}>
            {warn.map((w) => <p key={w.code} className="ic-warn"><IconTriangleAlert size={14} />{warningWords(w)}</p>)}
          </div>
        ) : null}
        <span className="ws-visually-hidden" aria-live="polite">{state[f] === "saved" ? C.saved : ""}</span>
      </div>
    );
  }

  function blur(f: string) {
    if (!touched.has(f)) return;
    const v = (local[f] ?? "").trim();
    if (v === textOf(client, f)) { setTouched((t) => new Set([...t].filter((x) => x !== f))); return; }
    void save({ [f]: v || null }, [f]);
  }

  return (
    <section className="ic-card" aria-labelledby="ic-card-t">
      <header className="ic-card__top">
        <h2 id="ic-card-t" className="ic-card__title">{C.title}</h2>
        <p className="ic-lead">{C.lead(name)}</p>
        {!canEdit ? <p className="ic-note">{C.readOnly}</p> : null}
      </header>

      <section className="ic-group" aria-labelledby="ic-g-certificate">
        <h3 id="ic-g-certificate" className="ic-group__h">{india ? C.groups.certificate : C.companyGroup}
          <Done ok={groupDone(checklist, rec, [...CARD_GROUPS[0].fields, "gst_certificate"])} /></h3>
        {/* D8: "outside India" is said once, here */}
        {!india ? <p className="ic-quiet">{C.abroad}</p> : null}
        {!india && !cert ? null : (
          <div className="ic-cert">
            {cert ? (
              <div className="ic-cert__filed">
                <p className="ic-cert__name">{C.filed(cert.filename, formatDate(cert.uploaded_at))}</p>
                <ItemState item={certItem} refused={refused} />
              </div>
            ) : null}
            {canEdit ? (
              <FilePicker compact={!!cert} accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
                          title={cert ? C.replace : C.upload} hint={C.uploadHint}
                          busyText={uploading ? C.reading : undefined} disabled={uploading} onFile={(f) => void upload(f)}
                          error={uploadError ? <p className="ic-field__err" role="alert">{uploadError}</p> : undefined} />
            ) : null}
            {justRead !== null ? <p className="ic-quiet" role="status">{C.readResult(justRead)}</p> : null}
            {shownUnconfirmed.length && canEdit ? (
              <div className="ic-banner">
                <p><IconScanText size={16} />{C.marker}</p>
                <button type="button" className="ws-btn ws-btn--sm" onClick={() => confirmReads(unconfirmed)}>
                  {C.confirmAll(shownUnconfirmed.length)}
                </button>
              </div>
            ) : null}
            {checklist.trade_name ? <p className="ic-quiet">{C.tradeName(checklist.trade_name)}</p> : null}
          </div>
        )}
        <div className="ic-fields">{CARD_GROUPS[0].fields.map(field)}</div>
      </section>

      {CARD_GROUPS.slice(1).map((g) => (
        <section key={g.key} className="ic-group" aria-labelledby={`ic-g-${g.key}`}>
          <h3 id={`ic-g-${g.key}`} className="ic-group__h">{C.groups[g.key]}<Done ok={groupDone(checklist, rec, g.fields)} /></h3>
          <div className="ic-fields">{g.fields.map(field)}</div>
        </section>
      ))}

      {checklist.verify_needed ? (
        <section className="ic-group" aria-labelledby="ic-g-check">
          <h3 id="ic-g-check" className="ic-group__h">{C.groups.check}<Done ok={!!checklist.verified} /></h3>
          <ul className="ic-links">
            <li><a href={GST_PORTAL} target="_blank" rel="noopener noreferrer">{C.gstLink}<IconExternal size={14} /></a></li>
            <li><a href={MCA_MASTER_DATA} target="_blank" rel="noopener noreferrer">{C.mcaLink}<IconExternal size={14} /></a></li>
          </ul>
          <p className="ic-tick__text">{C.tick}</p>
          {checklist.verified ? (
            <p className="ic-tick__done"><IconCheckCircle size={16} />{C.checkedBy(checklist.verified.by ?? "", formatDate(checklist.verified.at))}</p>
          ) : canEdit ? (
            <div className="ic-tick__act">
              <button type="button" className="ws-btn" disabled={!tickReady || ticking} aria-describedby={tickReady ? undefined : "ic-tick-why"}
                      onClick={() => void tick()}>{C.markChecked}</button>
              {!tickReady ? <p id="ic-tick-why" className="ic-quiet">{C.tickFirst}</p> : null}
              {tickError ? <p className="ic-field__err" role="alert">{tickError}</p> : null}
            </div>
          ) : <ItemState item={{ n: 11, key: "check", status: "missing", source: "profile" }} refused={refused} />}
        </section>
      ) : null}
    </section>
  );
}

export function warningWords(w: ClientChecklist["warnings"][number]): string {
  switch (w.code) {
    case "state_differs": return C.warnings.state_differs(w.gstin_state, w.office_state);
    case "state_unreadable": return C.warnings.state_unreadable;
    case "act_wording": return C.warnings.act_wording(w.year);
    case "name_differs": return C.warnings.name_differs(w.certificate_name, w.profile_name);
  }
}
