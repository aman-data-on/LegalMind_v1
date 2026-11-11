"use client";

/**
 * The ONE upload picker (UX Batch 2): a drop zone around the native file input. The input
 * stays real and focusable (keyboard, screen readers, a form's `required`), drawn as our
 * own button; a dropped file is also placed in the input, so a form that reads
 * `inputRef.current.files` on submit sees it either way. No new dependency.
 */

import { useId, useState, type Ref } from "react";

import { FEEDBACK_COPY } from "@/lib/labels";
import { IconUploadCloud } from "@/components/workspace/icons";

function size(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function FilePicker({
  onFile, chosen = null, accept = ".pdf,.docx,.md,.txt", disabled = false, required = false,
  hint = FEEDBACK_COPY.fileHint, title = FEEDBACK_COPY.dropTitle, busyText, primary = false,
  compact = false, inputRef, error, invalid, describedBy,
}: {
  onFile: (file: File | null) => void;
  /** the file the caller holds, shown by name and size */
  chosen?: File | null;
  accept?: string;
  disabled?: boolean;
  required?: boolean;
  hint?: string;
  title?: string;
  /** replaces the title while the caller works on the file ("Uploading…") */
  busyText?: string | undefined;
  /** the pick button is the view's primary action (an empty upload page) */
  primary?: boolean;
  /** a one-row zone inside a form */
  compact?: boolean;
  inputRef?: Ref<HTMLInputElement>;
  error?: React.ReactNode;
  invalid?: boolean | undefined;
  describedBy?: string | undefined;
}) {
  const [over, setOver] = useState(false);
  const hintId = useId();
  function drop(zone: HTMLElement, file: File | null) {
    if (!file || disabled) return;
    const input = zone.querySelector<HTMLInputElement>('input[type="file"]');
    if (input && typeof DataTransfer !== "undefined") {
      const carried = new DataTransfer();
      carried.items.add(file);
      input.files = carried.files;
    }
    onFile(file);
  }
  return (
    <div className={`ws-drop lm-drop${compact ? " lm-drop--compact" : ""}${over ? " ws-drop--over" : ""}`}
         data-disabled={disabled || undefined}
         onDragOver={(event) => { event.preventDefault(); if (!disabled) setOver(true); }}
         // only when the pointer leaves the zone itself, not one of its children
         onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setOver(false); }}
         onDrop={(event) => { event.preventDefault(); setOver(false); drop(event.currentTarget, event.dataTransfer.files?.[0] ?? null); }}>
      {compact ? null : <span className="ws-drop__icon" aria-hidden="true"><IconUploadCloud size={28} /></span>}
      <p className="ws-drop__title" aria-live="polite">
        {busyText ?? (chosen ? chosen.name : title)}
      </p>
      {!busyText ? (
        <p className="ws-drop__or">{chosen ? size(chosen.size) : FEEDBACK_COPY.dropOr}</p>
      ) : null}
      <label className={`ws-btn${primary && !chosen ? " ws-btn--primary" : ""} ws-drop__pick`} data-disabled={disabled || undefined}>
        {chosen ? FEEDBACK_COPY.chooseAnother : FEEDBACK_COPY.chooseFile}
        <input ref={inputRef} type="file" accept={accept} className="ws-visually-hidden"
               disabled={disabled} required={required} aria-invalid={invalid || undefined}
               aria-describedby={[hintId, describedBy].filter(Boolean).join(" ")}
               onChange={(event) => onFile(event.target.files?.[0] ?? null)} />
      </label>
      <span className="ws-drop__hint" id={hintId}>{hint}</span>
      {error}
    </div>
  );
}
