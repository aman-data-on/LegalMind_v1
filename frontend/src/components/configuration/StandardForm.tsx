"use client";

/**
 * Edit a ratified Company Standard as a form, not as JSON.
 *
 * WHY THIS REPLACES A TEXTAREA. Changing the organization's legal position used to
 * mean hand-editing one `<textarea>` holding the whole `company_standard` object.
 * To move a period from 21 to 30 a Legal person had to find the right key inside a
 * nested object and retype it without breaking the syntax — and nothing checked the
 * result: `RequirementVersionCreate` takes `dict[str, Any]`
 * (`backend/legalmind/api/schemas.py`), so a malformed standard saved cleanly and
 * failed days later at publish with "configuration is incomplete: …".
 *
 * WHY THAT DOES NOT BREAK RULE 21. The screen's header cites rule 21: a
 * helpful-looking placeholder would become the organization's legal position by
 * accident. That stays in force, and this form is the one write path where it
 * cannot bite — every value on screen is the organization's OWN stored value,
 * read back from a ratified standard. Nothing here defaults, suggests or
 * pre-selects; `draftFromStandard({})` returning an all-empty draft is asserted by
 * a test. Rule 21 forbids inventing legal content, not structure.
 *
 * WHAT IS SAFE ABOUT A FORM THAT DOES NOT MODEL EVERY KEY. `toStandard` spreads the
 * stored standard first at every level of nesting, so keys with no control —
 * `extraction.units`, `extraction.bases`, `general_scope`, `composite_phrases` —
 * survive byte-identical. The form cannot delete a position it does not display.
 * Where one of those genuinely needs editing, the advanced section hands over the
 * raw JSON and says plainly that it is doing so.
 *
 * Locked rule 16 is unchanged: saving APPENDS a new version, no existing version is
 * modified, and nothing reaches a Review until it is published into a snapshot.
 */

import { useId, useRef, useState } from "react";

import { ErrorBanner } from "@/components/Feedback";
import { PhraseList } from "@/components/configuration/PhraseList";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
  APPLICABILITY_OPTIONS, CONSTITUTION_BASES, DEFINITIONAL_UNIT_PAIRS, PRESENCE_OPTIONS,
  draftFromStandard, toStandard, unitPairKey, validateStandard,
  type EvaluatorKind, type StandardDraft,
} from "@/lib/companyStandard";
import { api } from "@/lib/api";
import { DOCUMENT_TYPES } from "@/lib/documentTypes";
import type { RequirementVersion } from "@/lib/types";

/** Human wording for the field keys `validateStandard` returns, for the summary. */
const FIELD_LABELS: Record<string, string> = {
  document_type: "Document type",
  scope_key: "Scope key",
  applicability: "Applicability",
  constitution_section: "Constitution section",
  constitution_topic: "Constitution topic",
  constitution_basis: "Basis",
  preferred: "Value",
  unit: "Unit",
  basis: "Measured against",
  expected_presence: "Expected",
  unit_conversions: "Unit conversions",
};

export function StandardForm({
  requirementId,
  version,
  onClose,
  onSaved,
}: {
  requirementId: string;
  version: RequirementVersion;
  onClose: () => void;
  onSaved: () => void;
}) {
  const stored = version.company_standard ?? {};
  const evaluator: EvaluatorKind =
    version.evaluator_type === "PRESENCE" ? "PRESENCE" : "NUMERIC_COMPARISON";
  // GP-1: the fields model PRESENCE and NUMERIC_COMPARISON only. Any other kind (a
  // CATEGORICAL list of allowed values) opens as its JSON, never as a misdescribed form.
  const modelled = version.evaluator_type === "PRESENCE"
    || version.evaluator_type === "NUMERIC_COMPARISON";

  const [draft, setDraft] = useState<StandardDraft>(() => draftFromStandard(stored));
  const [reason, setReason] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [serverError, setServerError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  // The escape hatch. While it is on, the JSON is authoritative and every field
  // above is disabled — two editable sources of truth for one object is how a
  // change gets silently discarded.
  const [rawMode, setRawMode] = useState(!modelled);
  const [rawText, setRawText] = useState(() => JSON.stringify(stored, null, 2));
  const [rawError, setRawError] = useState<string | null>(null);

  const summaryRef = useRef<HTMLDivElement>(null);
  const uid = useId();
  const fieldId = (key: string) => `${uid}-${key}`;
  const errorId = (key: string) => `${uid}-${key}-error`;

  const set = <K extends keyof StandardDraft>(key: K) => (value: StandardDraft[K]) =>
    setDraft((current) => ({ ...current, [key]: value }));

  /** Inline error beneath a control, referenced by the control's aria-describedby. A
   *  render helper, not a component declared in render (QA-080: that remounted every
   *  error on each keystroke). */
  const fieldError = (name: string) => errors[name] ? (
    <p className="ws-field__error" id={errorId(name)} role="alert">
      {errors[name]}
    </p>
  ) : null;

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setServerError(null);
    setRawError(null);

    let payload: Record<string, unknown>;
    if (rawMode) {
      // The screen's previous unguarded `JSON.parse` put a raw SyntaxError in the
      // error banner. A stray comma is a typo, not a system failure.
      try {
        const parsed: unknown = JSON.parse(rawText);
        if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
          setRawError("The standard must be a JSON object.");
          return;
        }
        payload = parsed as Record<string, unknown>;
      } catch {
        setRawError("This is not valid JSON — check for a missing comma, quote or brace.");
        return;
      }
    } else {
      const found = validateStandard(draft, stored, evaluator);
      setErrors(found);
      if (Object.keys(found).length > 0) {
        // Move focus to the summary rather than to the first field: the reader
        // needs to know how many problems there are before being dropped into one.
        summaryRef.current?.focus();
        return;
      }
      payload = toStandard(draft, stored);
    }

    setBusy(true);
    try {
      await api.updateCompanyStandard(requirementId, {
        company_standard: payload,
        reason,
      });
      onSaved();
    } catch (cause) {
      setServerError(cause);
    } finally {
      setBusy(false);
    }
  }

  const disabled = busy || rawMode;
  const errorKeys = Object.keys(errors);
  const jsonBox = (
    <>
      <textarea
        id={fieldId("raw")}
        className="ws-codearea"
        rows={12}
        value={rawText}
        disabled={!rawMode || busy}
        aria-describedby={rawError ? `${uid}-raw-error` : `${uid}-raw-hint`}
        onChange={(event) => setRawText(event.target.value)}
      />
      {rawError ? (
        <p className="ws-field__error" id={`${uid}-raw-error`} role="alert">{rawError}</p>
      ) : null}
    </>
  );

  return (
    <form className="ws-stdform" onSubmit={submit}>
      <h4 className="ws-intake__title">Company Standard — from v{version.version_number}</h4>
      <p className="ws-pane__note">
        Saving adds a new version; earlier versions stay unchanged. It affects no review until it is published.
      </p>

      <ErrorBanner error={serverError} />

      {errorKeys.length > 0 ? (
        <div
          className="ws-state ws-state--error ws-errsum"
          role="alert"
          tabIndex={-1}
          ref={summaryRef}
        >
          <p>
            {errorKeys.length === 1
              ? "One field needs attention before this can be saved."
              : `${errorKeys.length} fields need attention before this can be saved.`}
          </p>
          <ul className="ws-errsum__list">
            {errorKeys.map((key) => (
              <li key={key}>
                <a href={`#${fieldId(key)}`}>{FIELD_LABELS[key] ?? key}</a>: {errors[key]}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {modelled ? (
        <>
      {/* ── What this standard applies to ─────────────────────────────── */}
      <section className="ws-formsec">
        <h5>What this standard applies to</h5>
        <p className="ws-pane__note">
          A standard applies when a document has the clause. The type below is a hint, not a filter.
        </p>
        <div className="ws-formgrid">
          <div className="ws-field">
            <label className="ws-field__label" htmlFor={fieldId("document_type")}><>Document type <span className="ws-field__req" aria-hidden="true">*</span><span className="ws-visually-hidden">(required)</span></></label>
            <Select
              value={draft.document_type}
              onValueChange={set("document_type")}
              disabled={disabled}
            >
              <SelectTrigger
                id={fieldId("document_type")}
                aria-describedby={errors.document_type ? errorId("document_type") : undefined}
              >
                <SelectValue placeholder="Not chosen" />
              </SelectTrigger>
              <SelectContent>
                {DOCUMENT_TYPES.map((type) => (
                  <SelectItem key={type.code} value={type.code}>{type.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            {fieldError("document_type")}
          </div>

          <div className="ws-field">
            <label className="ws-field__label" htmlFor={fieldId("scope_key")}><>Scope key <span className="ws-field__req" aria-hidden="true">*</span><span className="ws-visually-hidden">(required)</span></></label>
            <input
              id={fieldId("scope_key")}
              value={draft.scope_key}
              disabled={disabled}
              aria-describedby={errors.scope_key ? errorId("scope_key") : `${uid}-scope-hint`}
              onChange={(event) => set("scope_key")(event.target.value)}
            />
            <p className="ws-field__help" id={`${uid}-scope-hint`}>
              Which clause this position is compared with.
            </p>
            {fieldError("scope_key")}
          </div>

          <div className="ws-field">
            <label className="ws-field__label" htmlFor={fieldId("applicability")}>Applicability</label>
            <Select
              value={draft.applicability}
              onValueChange={set("applicability")}
              disabled={disabled}
            >
              <SelectTrigger
                id={fieldId("applicability")}
                aria-describedby={`${uid}-applicability-hint`}
              >
                <SelectValue placeholder="Not stated" />
              </SelectTrigger>
              <SelectContent>
                {APPLICABILITY_OPTIONS.map((option) => (
                  <SelectItem key={option.code} value={option.code}>{option.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="ws-field__help" id={`${uid}-applicability-hint`}>
              If left unset, the standard is treated as required.
            </p>
            {fieldError("applicability")}
          </div>
        </div>
      </section>

      {/* ── Where the position comes from ─────────────────────────────── */}
      <section className="ws-formsec">
        <h5>Where this position comes from</h5>
        <p className="ws-pane__note">
          Explanations cite these fields. Publishing is refused if they do not agree.
        </p>
        <div className="ws-formgrid">
          <div className="ws-field">
            <label className="ws-field__label" htmlFor={fieldId("constitution_version")}>Constitution version</label>
            <input
              id={fieldId("constitution_version")}
              value={draft.constitution_version}
              disabled={disabled}
              onChange={(event) => set("constitution_version")(event.target.value)}
            />
          </div>

          <div className="ws-field">
            <label className="ws-field__label" htmlFor={fieldId("constitution_section")}>Section</label>
            <input
              id={fieldId("constitution_section")}
              value={draft.constitution_section}
              disabled={disabled}
              aria-describedby={
                errors.constitution_section ? errorId("constitution_section") : `${uid}-section-hint`
              }
              onChange={(event) => set("constitution_section")(event.target.value)}
            />
            <p className="ws-field__help" id={`${uid}-section-hint`}>
              Required, except for a document-only or retired standard.
            </p>
            {fieldError("constitution_section")}
          </div>

          <div className="ws-field">
            <label className="ws-field__label" htmlFor={fieldId("constitution_topic")}>Topic</label>
            <input
              id={fieldId("constitution_topic")}
              value={draft.constitution_topic}
              disabled={disabled}
              aria-describedby={
                errors.constitution_topic ? errorId("constitution_topic") : undefined
              }
              onChange={(event) => set("constitution_topic")(event.target.value)}
            />
            {fieldError("constitution_topic")}
          </div>

          <div className="ws-field">
            <label className="ws-field__label" htmlFor={fieldId("constitution_basis")}>Basis</label>
            <Select
              value={draft.constitution_basis}
              onValueChange={set("constitution_basis")}
              disabled={disabled}
            >
              <SelectTrigger
                id={fieldId("constitution_basis")}
                aria-describedby={
                  errors.constitution_basis ? errorId("constitution_basis") : undefined
                }
              >
                <SelectValue placeholder="Not chosen" />
              </SelectTrigger>
              <SelectContent>
                {CONSTITUTION_BASES.map((basis) => (
                  <SelectItem key={basis.code} value={basis.code}>{basis.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            {fieldError("constitution_basis")}
          </div>
        </div>
      </section>

      {/* ── The position itself ───────────────────────────────────────── */}
      <section className="ws-formsec">
        <h5>The position</h5>
        {evaluator === "NUMERIC_COMPARISON" ? (
          <>
            <p className="ws-pane__note">
              What we require, and the words used to read the client&rsquo;s clause.
            </p>
            <div className="ws-formgrid">
              <div className="ws-field">
            <label className="ws-field__label" htmlFor={fieldId("preferred")}>Value</label>
                <input
                  id={fieldId("preferred")}
                  type="number"
                  step="any"
                  value={draft.preferred}
                  disabled={disabled}
                  aria-describedby={errors.preferred ? errorId("preferred") : undefined}
                  onChange={(event) => set("preferred")(event.target.value)}
                />
                {fieldError("preferred")}
              </div>

              <div className="ws-field">
            <label className="ws-field__label" htmlFor={fieldId("unit")}>Unit</label>
                <input
                  id={fieldId("unit")}
                  value={draft.unit}
                  disabled={disabled}
                  aria-describedby={errors.unit ? errorId("unit") : undefined}
                  onChange={(event) => set("unit")(event.target.value)}
                />
                {fieldError("unit")}
              </div>

              <div className="ws-field">
            <label className="ws-field__label" htmlFor={fieldId("basis")}>Measured against</label>
                <input
                  id={fieldId("basis")}
                  value={draft.basis}
                  disabled={disabled}
                  aria-describedby={errors.basis ? errorId("basis") : undefined}
                  onChange={(event) => set("basis")(event.target.value)}
                />
                {fieldError("basis")}
              </div>
            </div>

            <div className="ws-field">
            <label className="ws-field__label" htmlFor={fieldId("cap_phrases")}>Phrases that state a limit</label>
              <PhraseList
                id={fieldId("cap_phrases")}
                value={draft.cap_phrases}
                onChange={set("cap_phrases")}
                disabled={disabled}
                describedBy={`${uid}-cap-count`}
              />
              <p className="ws-phrases__count" id={`${uid}-cap-count`}>
                {draft.cap_phrases.length === 1
                  ? "1 phrase"
                  : `${draft.cap_phrases.length} phrases`}
              </p>
            </div>

            <div className="ws-field">
            <label className="ws-field__label" htmlFor={fieldId("unlimited_phrases")}>Phrases that state no limit</label>
              <PhraseList
                id={fieldId("unlimited_phrases")}
                value={draft.unlimited_phrases}
                onChange={set("unlimited_phrases")}
                disabled={disabled}
                describedBy={`${uid}-unlimited-count`}
              />
              <p className="ws-phrases__count" id={`${uid}-unlimited-count`}>
                {draft.unlimited_phrases.length === 1
                  ? "1 phrase"
                  : `${draft.unlimited_phrases.length} phrases`}
              </p>
            </div>
          </>
        ) : (
          <div className="ws-field">
            <label className="ws-field__label" htmlFor={fieldId("expected_presence")}>Expected</label>
            <Select
              value={draft.expected_presence}
              onValueChange={set("expected_presence")}
              disabled={disabled}
            >
              <SelectTrigger
                id={fieldId("expected_presence")}
                aria-describedby={
                  errors.expected_presence ? errorId("expected_presence") : undefined
                }
              >
                <SelectValue placeholder="Not stated" />
              </SelectTrigger>
              <SelectContent>
                {PRESENCE_OPTIONS.map((option) => (
                  <SelectItem key={option.code} value={option.code}>{option.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            {fieldError("expected_presence")}
          </div>
        )}

        {/*
          The Legal Rule is shown, not hidden, and not editable. There is exactly
          one approved Legal Rule (owner, 2026-08-20) and this screen is not where
          it changes. Rendering it keeps the form honest about what will be saved.
          When the response omits it there is NO marker of any kind (52.4,
          SEC-07/LEGAL-02) — absence is indistinguishable from having none.
        */}
        {version.legal_rule ? (
          <p className="ws-stated">
            Legal Rule{" "}
            <span className="ws-stated__value">{version.legal_rule.rule_type}</span> — carried forward unchanged. It is not edited here.
          </p>
        ) : null}
      </section>

      {/* ── Advanced ──────────────────────────────────────────────────── */}
      <details className="ws-formsec">
        <summary>Advanced</summary>

        <div className="ws-field">
            <label className="ws-field__label" htmlFor={fieldId("unit_conversions")}>Unit conversions the engine may apply</label>
          <p className="ws-field__help" id={`${uid}-conversions-hint`}>
            Only exact conversions are allowed. Days and months are not, because a month is not always thirty days.
          </p>
          <ul className="ws-checks" aria-describedby={`${uid}-conversions-hint`}>
            {DEFINITIONAL_UNIT_PAIRS.map((pair) => {
              const key = unitPairKey(pair);
              const id = fieldId(`conv-${key}`);
              return (
                <li key={key} className="ws-check">
                  <Checkbox
                    id={id}
                    checked={draft.unit_conversions.includes(key)}
                    disabled={disabled}
                    onCheckedChange={(checked) =>
                      set("unit_conversions")(
                        checked === true
                          ? [...draft.unit_conversions, key]
                          : draft.unit_conversions.filter((k) => k !== key),
                      )
                    }
                  />
                  <label htmlFor={id} className="ws-check__label">
                    {pair.from} → {pair.to}
                  </label>
                </li>
              );
            })}
          </ul>
          {fieldError("unit_conversions")}
        </div>

        <div className="ws-field">
            <label className="ws-field__label" htmlFor={fieldId("not_applicable_to")}>Never applies to these document types</label>
          <ul className="ws-checks">
            {DOCUMENT_TYPES.map((type) => {
              const id = fieldId(`na-${type.code}`);
              return (
                <li key={type.code} className="ws-check">
                  <Checkbox
                    id={id}
                    checked={draft.not_applicable_to.includes(type.code)}
                    disabled={disabled}
                    onCheckedChange={(checked) =>
                      set("not_applicable_to")(
                        checked === true
                          ? [...draft.not_applicable_to, type.code]
                          : draft.not_applicable_to.filter((c) => c !== type.code),
                      )
                    }
                  />
                  <label htmlFor={id} className="ws-check__label">{type.label}</label>
                </li>
              );
            })}
          </ul>
        </div>

        <div className="ws-field">
            <label className="ws-field__label" htmlFor={fieldId("raw")}>Edit the stored JSON directly</label>
          <p className="ws-field__help" id={`${uid}-raw-hint`}>
            For settings this form does not show. While this is on, the JSON is saved and the fields above are disabled.
          </p>
          <label className="ws-check" htmlFor={fieldId("raw-toggle")} style={{ marginBottom: "0.5rem" }}>
            <Checkbox
              id={fieldId("raw-toggle")}
              checked={rawMode}
              disabled={busy}
              onCheckedChange={(checked) => {
                const on = checked === true;
                // Entering raw mode starts from what the FORM would save, so the
                // edits made above are the starting point rather than being lost.
                if (on) setRawText(JSON.stringify(toStandard(draft, stored), null, 2));
                else setDraft(draftFromStandard(safeParse(rawText) ?? stored));
                setRawError(null);
                setRawMode(on);
              }}
            />
            <span className="ws-check__label">Use the JSON below instead of the fields above</span>
          </label>
          {jsonBox}
        </div>
      </details>
        </>
      ) : (
        <section className="ws-formsec">
          <div className="ws-field">
            <label className="ws-field__label" htmlFor={fieldId("raw")}>The stored standard</label>
            <p className="ws-field__help" id={`${uid}-raw-hint`}>
              This kind of standard is edited as JSON for now.
            </p>
            {jsonBox}
          </div>
        </section>
      )}

      {/* ── Why ───────────────────────────────────────────────────────── */}
      <section className="ws-formsec">
        <div className="ws-field">
            <label className="ws-field__label" htmlFor={fieldId("reason")}><>Reason for the change <span className="ws-field__req" aria-hidden="true">*</span><span className="ws-visually-hidden">(required)</span></></label>
          <input
            id={fieldId("reason")}
            value={reason}
            required
            disabled={busy}
            aria-describedby={`${uid}-reason-hint`}
            onChange={(event) => setReason(event.target.value)}
          />
          <p className="ws-field__help" id={`${uid}-reason-hint`}>
            Recorded in the audit trail.
          </p>
        </div>
      </section>

      <button type="submit" className="ws-btn ws-btn--primary" disabled={busy}>
        {busy ? "Saving…" : "Save as a new version"}
      </button>{" "}
      <button type="button" className="ws-btn ws-btn--link" onClick={onClose} disabled={busy}>
        Cancel
      </button>
    </form>
  );
}

function safeParse(text: string): Record<string, unknown> | null {
  try {
    const parsed: unknown = JSON.parse(text);
    return parsed !== null && typeof parsed === "object" && !Array.isArray(parsed)
      ? (parsed as Record<string, unknown>)
      : null;
  } catch {
    return null;
  }
}
