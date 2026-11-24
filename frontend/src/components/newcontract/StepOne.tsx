"use client";

/**
 * Step 1 of the intake — template and client (batch 7 review). Only a contract type with a
 * published template is offered; the MSA is one contract from one entity for every brand
 * (AM-341), so its company is said, not asked. The side panel names what the contract will
 * need from the client.
 */

import Link from "@/components/AppLink";
import { useEffect, useState } from "react";

import { api, describeError } from "@/lib/api";
import { INTAKE_COPY as C } from "@/lib/labels";
import { BRANDS, DOC_TYPES, askedNow, type PublishedTemplate } from "@/lib/newContract";
import { brandLabel, templatesFor, type TemplateCardData } from "@/lib/templates";
import { IconCheckCircle } from "@/components/workspace/icons";
import type { Counterparty } from "@/lib/types";
import { EmptyState, LoadingState } from "@/components/Feedback";
import { CardDownload, TemplateCard } from "@/components/templates/TemplateCard";
import { UploadContractDialog } from "@/components/workspace/UploadContractDialog";
import { toastFailure } from "@/components/Toast";

import { ClientPicker } from "./ClientPicker";

export function StepOne({ published, awaiting, wanted, onStart, convertFor = null }: {
  published: PublishedTemplate[] | null;
  /** templates everyone can see but nobody can use yet (`AM-316` r5) */
  awaiting: TemplateCardData[];
  /** `?template=<key>` — the deep link from the Templates page */
  wanted: string | null;
  onStart: (t: PublishedTemplate, client: Counterparty, brand: string | null) => Promise<void>;
  /** `?convert=<contract>` — "Convert to our paper": the deal's client is chosen already */
  convertFor?: string | null;
}) {
  const link = wanted && published ? published.find((x) => x.template_key === wanted) : undefined;
  const types = DOC_TYPES.filter((t) => published?.some((x) => x.doc_type === t.id && !x.awaiting_approval));
  const [docTypeSet, setDocType] = useState<string | null>(null);
  const [brandSet, setBrand] = useState<string | null>(null);
  const [chosenSet, setChosen] = useState<string | null>(null);
  const docType = docTypeSet ?? link?.doc_type ?? (types.length === 1 ? types[0]!.id : null);
  const brands = BRANDS.filter((b) => published?.some((x) => x.doc_type === docType && x.brand === b && !x.awaiting_approval));
  // one brand with a template of this type (the MSA: one contract for every brand) is said, not asked
  const brand = brandSet ?? link?.brand ?? (brands.length === 1 ? brands[0]! : null);
  const choices = docType && brand && published ? templatesFor(published, docType, brand) : [];
  const template = choices.length === 1 ? choices[0] : choices.find((t) => t.id === (chosenSet ?? link?.id));
  const waiting = docType ? awaiting.filter((t) => t.doc_type === docType) : [];
  const [client, setClient] = useState<Counterparty | null>(null);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    if (!convertFor) return;
    let live = true;
    api.contract(convertFor)
      .then((c) => (c.counterparty_id ? api.counterparty(c.counterparty_id) : null))
      .then((c) => { if (live && c) setClient((now) => now ?? c); })
      .catch(toastFailure("The deal’s client could not be loaded"));
    return () => { live = false; };
  }, [convertFor]);

  async function start() {
    if (!template || !client) return;
    setBusy(true); setFailure(null);
    try { await onStart(template, client, brand); } catch (e) { setFailure(describeError(e)); setBusy(false); }
  }

  if (published === null) return <div className="ic-main"><LoadingState rows={4} /></div>;
  if (!types.length) {
    return (
      <div className="ic-main">
        <EmptyState title={C.noTemplate} body={C.noTemplateFix}
                    action={<button type="button" className="ws-btn ws-btn--primary" onClick={() => setUploading(true)}>{C.uploadInstead}</button>} />
        {uploading ? <UploadContractDialog firstRun={false} onClose={() => setUploading(false)} /> : null}
      </div>
    );
  }

  const form = (
    <div className="ic-main">
      <section className="ic-section" aria-labelledby="ic-what">
        <h2 id="ic-what" className="ic-section__h">{C.whatTitle}</h2>
        {types.length > 1 ? (
          <div className="ic-options" role="radiogroup" aria-labelledby="ic-what">
            {types.map((t) => (
              <label key={t.id} className="nc-option">
                <input type="radio" name="ic-type" checked={docType === t.id} onChange={() => { setDocType(t.id); setBrand(null); setChosen(null); }} />
                <span className="nc-item__l1">{t.name}</span><span className="nc-item__l2">{t.long}</span>
              </label>
            ))}
          </div>
        ) : null}
        {brands.length > 1 ? (
          <fieldset className="ic-options">
            <legend className="ic-field__label">{C.whichCompany}</legend>
            {brands.map((b) => (
              <label key={b} className="nc-option">
                <input type="radio" name="ic-brand" checked={brand === b} onChange={() => setBrand(b)} />
                <span className="nc-item__l1">{brandLabel(b)}</span>
              </label>
            ))}
          </fieldset>
        ) : docType === "MSA" ? <p className="ic-quiet">{C.fromLine}</p> : null}
        {wanted && !link ? <p className="ic-note" role="status">{C.linkGone}</p> : null}
        {choices.length > 1 ? (
          <fieldset className="ic-cards">
            <legend className="ic-field__label">{C.whichOne(docType!)}</legend>
            {choices.map((t) => (
              <TemplateCard key={t.id} t={t} radio={{ name: "nc-template", checked: template?.id === t.id, onChange: () => setChosen(t.id) }}
                            actions={<CardDownload t={t} />} />
            ))}
          </fieldset>
        ) : template ? (
          <div className="ic-cards">
            <h3 className="ic-field__label">{C.ourTemplate}</h3>
            <TemplateCard t={template} actions={<CardDownload t={template} />} />
          </div>
        ) : null}
        {/* benchmark 6: what the deal will ask, before committing (the card owns the client's facts) */}
        {template ? <p className="ic-quiet">{C.dealAsks(askedNow(template.questions
          .filter((q) => !(template.client_questions ?? []).includes(q.key)), {}).map((q) => q.label))}</p> : null}
        {waiting.length ? (
          <p className="ic-quiet">{C.awaiting(docType!)} <Link className="nc-link" href="/templates">See Templates</Link></p>
        ) : null}
      </section>
      {template ? (
        <section className="ic-section" aria-labelledby="ic-who">
          <h2 id="ic-who" className="ic-section__h">{C.whoTitle}</h2>
          <ClientPicker value={client} onChange={setClient} />
        </section>
      ) : null}
      {failure ? <p className="nc-error" role="alert">{failure}</p> : null}
    </div>
  );

  return (
    <>
      <div className="ic-grid">
        {form}
        <aside className="ic-panel" aria-label={C.tabs.needed}>
          <h2 className="ic-needed__h">{C.title}</h2>
          <p className="ic-quiet">{client ? C.detailsMissing(client.details_missing ?? 0) : C.panelLead}</p>
          <ul className="ic-needed__list ic-needed__list--plain">
            {[...Object.entries(C.items).filter(([k]) => k !== "agreement_date"), ["check", C.checkLine] as const].map(([k, w]) => (
              <li key={k}>{w}{client && !client.details_missing && client.details_verified_at
                ? <span className="ic-state" data-tone="done"><IconCheckCircle size={14} />{C.onFileRow}</span> : null}</li>
            ))}
          </ul>
        </aside>
      </div>
      <div className="ic-bar">
        <span className="ic-quiet">{!template || !client ? C.chooseFirst : ""}</span>
        <button type="button" className="ws-btn ws-btn--primary" disabled={!template || !client || busy} onClick={() => void start()}>
          {busy ? C.starting : C.continue}
        </button>
      </div>
    </>
  );
}
