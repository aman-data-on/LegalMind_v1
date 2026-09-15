"use client";

/**
 * A list of extraction phrases, edited as chips.
 *
 * WHY NOT A TEXTAREA, ONE PER LINE. These are the phrases the extractor matches a
 * counterparty's clause against — `LIABILITY-MSA-001` carries eight. In a textarea
 * they are one blob where a stray newline silently splits a phrase in half, and
 * nothing on screen says how many there are. As chips the count is visible, each
 * phrase is individually removable, and a partly-typed one cannot be saved by
 * accident.
 *
 * WHY NOT A LIBRARY. shadcn/ui has no tag-input primitive and neither does Radix,
 * so this composes a plain `<input>` with the design system's own chip styling.
 * Nothing here needs a dependency (rule 19).
 *
 * `ui-ux-pro-max` "Chip Collection Reflow": the collection WRAPS. It never scrolls
 * horizontally and never truncates a phrase — a clipped legal phrase reads as a
 * different phrase. Each chip carries a real `<button>` with an accessible name
 * rather than a bare "×" glyph, and the count below is the operable summary.
 *
 * RULE 21: this component proposes nothing. It has no suggestions, no datalist and
 * no default phrase. The placeholder names the ACTION ("Type a phrase and press
 * Enter"), never an example phrase — an example here would become the
 * organization's matching rule by accident.
 */

import { X } from "lucide-react";
import { useRef, useState } from "react";

export function PhraseList({
  id,
  value,
  onChange,
  disabled,
  describedBy,
}: {
  id: string;
  value: string[];
  onChange: (next: string[]) => void;
  disabled?: boolean;
  describedBy?: string;
}) {
  const [pending, setPending] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  function commit(raw: string) {
    const phrase = raw.trim();
    // A duplicate is not an error worth a message — the phrase is already in the
    // list, which is what the person wanted. Silently keeping one is the honest
    // outcome; adding a second would make the count lie.
    if (phrase && !value.includes(phrase)) onChange([...value, phrase]);
    setPending("");
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      // Enter must not submit the surrounding form while a phrase is half-typed.
      event.preventDefault();
      commit(pending);
    } else if (event.key === "Backspace" && pending === "" && value.length > 0) {
      onChange(value.slice(0, -1));
    }
  }

  return (
    <div className="ws-phrases" data-disabled={disabled ? "" : undefined}>
      <ul className="ws-phrases__list">
        {value.map((phrase) => (
          <li key={phrase} className="ws-phrase">
            <span className="ws-phrase__text">{phrase}</span>
            <button
              type="button"
              className="ws-phrase__remove"
              disabled={disabled}
              // The phrase itself is in the name, so a screen reader announces
              // WHICH one is being removed — "Remove" alone is eleven identical
              // buttons.
              aria-label={`Remove ${phrase}`}
              onClick={() => {
                onChange(value.filter((p) => p !== phrase));
                inputRef.current?.focus();
              }}
            >
              <X size={13} aria-hidden="true" />
            </button>
          </li>
        ))}
      </ul>
      <input
        ref={inputRef}
        id={id}
        className="ws-phrases__input"
        type="text"
        value={pending}
        disabled={disabled}
        aria-describedby={describedBy}
        placeholder="Type a phrase and press Enter"
        onChange={(event) => setPending(event.target.value)}
        onKeyDown={onKeyDown}
        // Committing on blur is deliberate: a half-typed phrase that is lost
        // because someone clicked Save is a change they cannot see they missed.
        onBlur={() => commit(pending)}
      />
    </div>
  );
}
