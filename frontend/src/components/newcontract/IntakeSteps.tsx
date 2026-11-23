"use client";

/**
 * The New contract intake's four steps (batch 7): a real sequence, so numbered. Each says
 * where it stands in words ("7 of 10 added", never a percentage); a step already reached is
 * a link back. At a phone's width the list becomes one line ("Step 2 of 4. Client details").
 */

import { INTAKE_COPY } from "@/lib/labels";
import { IconCheck } from "@/components/workspace/icons";

export type IntakeStep = 1 | 2 | 3 | 4;

export function IntakeSteps({ step, done, notes, onGo }: {
  step: IntakeStep;
  /** steps the server says are complete (client details on file, every answer given) */
  done: Partial<Record<IntakeStep, boolean>>;
  /** a step's own count, in words */
  notes?: Partial<Record<IntakeStep, string | undefined>>;
  /** a reached step's link; absent where the step cannot be opened yet */
  onGo?: ((s: IntakeStep) => void) | undefined;
}) {
  return (
    <nav className="ic-steps" aria-label="Steps">
      <p className="ic-steps__phone">{INTAKE_COPY.stepOf(step)}. {INTAKE_COPY.steps[step - 1]}
        {notes?.[step] ? <span className="ic-steps__note"> {notes[step]}</span> : null}</p>
      <ol>
        {INTAKE_COPY.steps.map((name, i) => {
          const n = (i + 1) as IntakeStep;
          const here = n === step;
          const inner = (
            <>
              <span className="ic-steps__n" data-done={done[n] || undefined}>
                {done[n] && !here ? <IconCheck size={14} /> : n}
              </span>
              <span className="ic-steps__name">{name}</span>
              {notes?.[n] ? <span className="ic-steps__note">{notes[n]}</span> : null}
            </>
          );
          return (
            <li key={name} {...(here ? { "aria-current": "step" as const } : {})}>
              {!here && onGo && n < 4 && (n < step || done[n])
                ? <button type="button" className="ic-steps__go" onClick={() => onGo(n)}>{inner}</button>
                : <span className="ic-steps__go">{inner}</span>}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
