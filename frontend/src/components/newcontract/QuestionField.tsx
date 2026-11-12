"use client";

/**
 * One question of the template (S5). The label above the field, Required or Optional in
 * words, help under the label, the field, then what is wrong with it (inline, as the
 * person types) — the IBM Carbon / Atlassian form order. A question with approved options
 * is a set of choices, never free text; a number says its range; a date is typed day,
 * month, year, as India writes it; a value our template fixes is text, never an input.
 * The server validates every answer.
 */

import { useState, type InputHTMLAttributes } from "react";

import { dateText, display, locked, outsideRange, parseDate, rangeWords, required, type Question } from "@/lib/newContract";

export const questionId = (key: string) => `nc-q-${key}`;

/** Where a value came from, and what changing it can do (`AM-286`): the client profile. */
export interface ProfileLink {
  /** the profile's value for this field, when it has one */
  value: string | null;
  /** the person changed the answer: offer to save it to the profile too */
  onUpdate?: () => void;
  state?: "saving" | "saved" | "error" | undefined;
}

function Label({ q, htmlFor }: { q: Question; htmlFor?: string }) {
  const Tag = htmlFor ? "label" : "span";
  return (
    <Tag className="nc-q__label" {...(htmlFor ? { htmlFor } : {})}>
      {q.label}
      <span className="nc-q__req">{required(q) ? "Required" : "Optional"}</span>
    </Tag>
  );
}

function DateInput({ value, onChange, ...rest }: { value: unknown; onChange: (v: string) => void }
  & Omit<InputHTMLAttributes<HTMLInputElement>, "value" | "onChange">) {
  const shown = typeof value === "string" ? dateText(value) : "";
  const [text, setText] = useState(shown);
  const [seen, setSeen] = useState(value);
  if (value !== seen) {       // the saved value changed underneath (a reload): show it
    setSeen(value);
    if (typeof value === "string" && parseDate(text) !== value) setText(dateText(value));
  }
  return (
    <input {...rest} type="text" inputMode="numeric" autoComplete="off" value={text}
           onChange={(e) => { setText(e.target.value); onChange(parseDate(e.target.value) ?? e.target.value); }} />
  );
}

export function QuestionField({ q, value, problem, profile, onChange }: {
  q: Question;
  value: unknown;
  /** the server's word on this answer, after a save */
  problem?: string | undefined;
  profile?: ProfileLink | undefined;
  onChange: (key: string, value: unknown) => void;
}) {
  const id = questionId(q.key);
  const helpId = `${id}-help`;
  const errId = `${id}-err`;
  const typed = typeof value === "string" ? value.trim() : value;
  const badDate = q.type === "date" && typeof typed === "string" && typed !== "" && !parseDate(typed)
    ? "Not a date yet. Type day, month and year, for example 10/11/2026." : null;
  const own = badDate ?? outsideRange(q, value);
  const message = own ?? (problem ? `${q.label} ${problem}` : null);
  const help = q.type === "date" ? `${q.help ? `${q.help} ` : ""}Day, month, year, for example 10/11/2026.` : q.help;
  const describedBy = [help ? helpId : null, message ? errId : null].filter(Boolean).join(" ") || undefined;
  const helpLine = help ? <p id={helpId} className="nc-q__help">{help}</p> : null;
  const error = message ? <p id={errId} className="nc-q__error">{message}</p> : null;

  if (locked(q)) {
    return (
      <div className="nc-q nc-q--fixed" id={id} tabIndex={-1}>
        <span className="nc-q__label">{q.label}</span>
        <p className="nc-q__fixed">{display(q, q.locked_value)}</p>
        <p className="nc-q__help">Fixed by our template</p>
      </div>
    );
  }

  const options: (string | number | boolean)[] | null = q.allowed?.length ? q.allowed
    : q.type === "bool" ? [true, false] : null;
  if (options && options.length <= 4) {
    return (
      <fieldset className="nc-q" id={id} tabIndex={-1} aria-describedby={describedBy}
                {...(message ? { "aria-invalid": true } : {})}>
        <legend className="nc-q__label">
          {q.label}<span className="nc-q__req">{required(q) ? "Required" : "Optional"}</span>
        </legend>
        {helpLine}
        <div className="nc-q__choices">
          {options.map((o) => (
            <label key={String(o)} className="nc-choice">
              <input type="radio" name={id} checked={value === o} onChange={() => onChange(q.key, o)} />
              <span>{display(q, o)}</span>
            </label>
          ))}
        </div>
        {error}
      </fieldset>
    );
  }

  const common = {
    id, "aria-describedby": describedBy, ...(message ? { "aria-invalid": true as const } : {}),
    ...(required(q) ? { "aria-required": true as const } : {}),
  };
  let input;
  if (options) {
    input = (
      <select {...common} value={value === undefined || value === null ? "" : String(value)}
              onChange={(e) => onChange(q.key, options.find((o) => String(o) === e.target.value) ?? "")}>
        <option value="">Choose…</option>
        {options.map((o) => <option key={String(o)} value={String(o)}>{display(q, o)}</option>)}
      </select>
    );
  } else if (q.type === "date") {
    input = <DateInput {...common} value={value} onChange={(v) => onChange(q.key, v)} />;
  } else if (q.type === "int") {
    const [lo, hi] = q.range ?? [null, null];
    input = (
      <input {...common} type="number" inputMode="numeric" step={1} {...(lo != null ? { min: lo } : {})}
             {...(hi != null ? { max: hi } : {})} value={String(value ?? "")}
             onChange={(e) => onChange(q.key, e.target.value)} />
    );
  } else if (/office|address/.test(q.role ?? q.key)) {
    input = <textarea {...common} rows={2} value={String(value ?? "")} onChange={(e) => onChange(q.key, e.target.value)} />;
  } else {
    input = <input {...common} type={q.type === "email" || /email/.test(q.role ?? "") ? "email" : "text"} value={String(value ?? "")}
                   onChange={(e) => onChange(q.key, e.target.value)} />;
  }
  const range = q.type === "int" ? rangeWords(q) : null;
  const iso = q.type === "date" && typeof typed === "string" ? parseDate(typed) : null;
  const same = profile?.value != null && typeof typed === "string" && typed === profile.value.trim();
  return (
    <div className="nc-q">
      <Label q={q} htmlFor={id} />
      {helpLine}
      <div className="nc-q__row">{input}{range ? <span className="nc-q__range">{range}</span> : null}
        {iso ? <span className="nc-q__range">{display(q, iso)}</span> : null}</div>
      {error}
      {same ? <p className="nc-q__from">From the client profile</p> : null}
      {profile && !same && typeof typed === "string" && typed && profile.onUpdate ? (
        <p className="nc-q__from nc-q__from--changed">
          {profile.state === "saved" ? "Client profile updated" : profile.value ? "Differs from the client profile" : "Not in the client profile yet"}
          {profile.state !== "saved" ? (
            <button type="button" className="nc-linkbtn" onClick={profile.onUpdate} disabled={profile.state === "saving"}>
              {profile.state === "saving" ? "Updating…" : "Also update the client profile"}
            </button>
          ) : null}
          {profile.state === "error" ? <span className="nc-q__error"> The profile was not updated.</span> : null}
        </p>
      ) : null}
    </div>
  );
}
