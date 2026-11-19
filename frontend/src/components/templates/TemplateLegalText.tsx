"use client";

/**
 * Wording only Legal can write on a template (`AM-412`, optional since `AM-414`): its own
 * words for Annexure 1 and for Annexure 2. Neither is needed for a final contract. The
 * fields start empty: this page never writes, suggests or prefills them (rules 7/21). Saving makes a draft of the clause that holds
 * the text; Legal approves that clause and publishes, as for any clause. The server
 * decides and refuses; this only asks and shows.
 */

import { useState } from "react";

import { api, describeError } from "@/lib/api";
import type { LegalTextPlace, TemplateDetail } from "@/lib/templates";

/** Send ``run``; on failure keep the form open with the server's words. */
export function useSend(onDone: () => Promise<void>) {
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

const COPY = {
  title: "Wording from Legal (optional)",
  lead: "Optional: Legal can add wording here. A final contract can be prepared without it. LegalMind does not "
    + "write or suggest these words. Type them exactly as the contract should print them, one paragraph per line.",
  place: {
    annexure_1: { label: "Annexure 1 wording", help: "Printed at the top of Annexure 1, above the order form tables." },
    precedence: { label: "Annexure 2 wording",
                  help: "Printed under the Annexure 2 title, after its opening line and before the agreed changes." },
  },
  notSupplied: "None added. Nothing is printed here.",
  notApproved: "Saved. Not approved yet: approve the clause that holds it, then publish.",
  approved: "Saved and approved.",
  published: "This version is published. To add wording, start a new version of the template.",
  openClause: "Open the clause",
  save: "Save text",
  saving: "Saving…",
  change: "Change text",
} as const;

function Place({ templateId, place, onDone, onSelect }: {
  templateId: string; place: LegalTextPlace; onDone: () => Promise<void>; onSelect: (clauseKey: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState("");
  const { busy, error, send } = useSend(onDone);
  const words = COPY.place[place.which];
  const id = `tpl-legaltext-${place.which}`;
  const form = place.editable && (editing || !place.supplied);
  return (
    <li>
      <span className="tpl-label" id={`${id}-name`}>{words.label}</span>
      <span className="tpl-pubrow__said">
        {place.supplied ? (place.approved ? COPY.approved : COPY.notApproved) : COPY.notSupplied}
      </span>
      {place.supplied && !form ? <p className="tpl-legaltext__words">{place.text}</p> : null}
      {form ? (
        <form className="tpl-form" onSubmit={(e) => {
          e.preventDefault();
          if (text.trim() && !busy) void send(() => api.supplyLegalText(templateId, place.which, text)).then((ok) => ok && setEditing(false));
        }}>
          <label htmlFor={id} className="ws-visually-hidden">{words.label}</label>
          <textarea id={id} className="tpl-reason" rows={4} maxLength={20000} required value={text}
                    aria-describedby={`${id}-help`} onChange={(e) => setText(e.target.value)} />
          <p id={`${id}-help`} className="tpl-help">{words.help}</p>
          {error ? <p className="tpl-error" role="alert">{error}</p> : null}
          <div className="tpl-actions__row">
            {place.supplied ? <button type="button" className="ws-btn" disabled={busy} onClick={() => setEditing(false)}>Cancel</button> : null}
            <button type="submit" className="ws-btn" disabled={busy || !text.trim()} aria-busy={busy || undefined}>
              {busy ? COPY.saving : COPY.save}</button>
          </div>
        </form>
      ) : place.editable ? (
        <span className="tpl-pubrow__where">
          {place.approved ? null : (
            <button type="button" className="tpl-link" onClick={() => onSelect(place.clause_key)}>{COPY.openClause}</button>
          )}
          <button type="button" className="tpl-link" onClick={() => { setText(place.text ?? ""); setEditing(true); }}>{COPY.change}</button>
        </span>
      ) : place.supplied ? null : <span className="tpl-pubrow__said">{COPY.published}</span>}
    </li>
  );
}

export function LegalText({ detail, onDone, onSelect }: {
  detail: TemplateDetail; onDone: () => Promise<void>; onSelect: (clauseKey: string) => void;
}) {
  const places = detail.legal_text ?? [];
  if (!places.length) return null;
  return (
    <div className="tpl-pubgroup" data-legal-text="optional">
      <h3>{COPY.title}</h3>
      <p className="tpl-help">{COPY.lead}</p>
      <ul>{places.map((p) => (
        <Place key={p.which} templateId={detail.id} place={p} onDone={onDone} onSelect={onSelect} />
      ))}</ul>
    </div>
  );
}
