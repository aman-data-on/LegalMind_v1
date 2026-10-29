"use client";

/**
 * The questions Ask puts to the reader before reviewing several documents together
 * (`AM-230`): each with why it matters, tappable options, and the default a skipped one
 * takes. Native radio and checkbox inputs in fieldsets, so it works with a keyboard and a
 * screen reader. Once answered (or when a later turn exists) it shows the answers only.
 */
import { useState } from "react";

import type { DealQuestion } from "@/lib/types";

import { IconInfo } from "./icons";

type Answers = Record<string, string | string[]>;

function initial(questions: DealQuestion[]): Answers {
  return Object.fromEntries(questions.map((q) => [q.id, q.default]));
}

/** The reader's answers in words, for their own message in the chat. */
export function answersText(questions: DealQuestion[], answers: Answers): string {
  return questions.map((q) => {
    const chosen = ([] as string[]).concat(answers[q.id] ?? q.default);
    const words = chosen.map((v) => q.options.find((o) => o.value === v)?.label ?? v);
    return `${q.text} ${words.join(", ")}.`;
  }).join("\n");
}

export function DealQuestions({ questions, onSubmit, disabled = false, settled }: {
  questions: DealQuestion[];
  onSubmit: (answers: Answers, text: string) => void;
  disabled?: boolean;
  /** Answers already given — the card is then read-only. */
  settled?: Answers | null;
}) {
  const [answers, setAnswers] = useState<Answers>(() => initial(questions));
  if (settled) {
    return (
      <dl className="ws-dealq ws-dealq--settled">
        {questions.map((q) => {
          const chosen = ([] as string[]).concat(settled[q.id] ?? q.default);
          return (
            <div key={q.id} className="ws-dealq__settled">
              <dt>{q.text}</dt>
              <dd>{chosen.map((v) => q.options.find((o) => o.value === v)?.label ?? v)
                .join(", ")}</dd>
            </div>
          );
        })}
      </dl>
    );
  }
  const set = (q: DealQuestion, value: string, on: boolean) => setAnswers((previous) => {
    if (!q.multiple) return { ...previous, [q.id]: value };
    const now = ([] as string[]).concat(previous[q.id] ?? []).filter((v) => v !== value);
    // "None" excludes every document, and a document excludes "None"
    if (!on) return { ...previous, [q.id]: now };
    return { ...previous, [q.id]: value === "none" ? ["none"]
      : [...now.filter((v) => v !== "none"), value] };
  });
  return (
    <form className="ws-dealq" onSubmit={(event) => {
      event.preventDefault();
      onSubmit(answers, answersText(questions, answers));
    }}>
      {questions.map((q) => {
        const chosen = ([] as string[]).concat(answers[q.id] ?? []);
        return (
          <fieldset key={q.id} className="ws-dealq__q" disabled={disabled}>
            <legend className="ws-dealq__text">{q.text}</legend>
            <p className="ws-dealq__why"><IconInfo size={14} />{q.why}</p>
            <div className="ws-dealq__options">
              {q.options.map((o) => (
                <label key={o.value} className="ws-dealq__option"
                       data-on={chosen.includes(o.value) ? "" : undefined}>
                  <input type={q.multiple ? "checkbox" : "radio"} name={`dealq-${q.id}`}
                         value={o.value} checked={chosen.includes(o.value)}
                         onChange={(event) => set(q, o.value, event.target.checked)} />
                  <span>{o.label}</span>
                </label>
              ))}
            </div>
          </fieldset>
        );
      })}
      <div className="ws-dealq__actions">
        <button type="submit" className="ws-btn ws-btn--primary" disabled={disabled}>
          Review with these answers
        </button>
        <button type="button" className="ws-btn" disabled={disabled}
                onClick={() => onSubmit(initial(questions),
                                        answersText(questions, initial(questions)))}>
          Skip — use the defaults
        </button>
      </div>
    </form>
  );
}
