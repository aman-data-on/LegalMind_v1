"use client";

/**
 * The ONE filter control (UX Batch 2, round 2). A filter is not a status, so it never looks
 * like a chip: a joined row of square-cornered segments (radius 4, a control-strength edge),
 * the count in caption type beside the word, no bubble. A segment whose count is 0 is not
 * shown (PLAIN-LANGUAGE §5) unless it is the one selected or marked `always`. When the row
 * does not fit its container it never clips or scrolls sideways: it becomes one native
 * select under the group's own name (DESIGN-FOUNDATION §2.2, WCAG 1.4.10). Presentation only: the counts and
 * what each filter keeps come from the caller.
 */

import { useLayoutEffect, useRef, useState } from "react";

export interface Segment<T extends string = string> {
  id: T;
  /** what the segment shows (may hold an icon) */
  label: React.ReactNode;
  /** the same words as plain text, for the collapsed select and the accessible name */
  text: string;
  count?: number | undefined;
  /** shown even at 0 ("All") */
  always?: boolean;
}

export function SegmentedFilter<T extends string>({ label, segments, value, onChange }: {
  /** the group's name ("Show changes") */
  label: string;
  segments: Segment<T>[];
  value: T;
  onChange: (id: T) => void;
}) {
  const shown = segments.filter((s) => s.always || s.id === value || s.count === undefined || s.count > 0);
  const box = useRef<HTMLDivElement | null>(null);
  const measure = useRef<HTMLDivElement | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  useLayoutEffect(() => {
    const outer = box.current, row = measure.current;
    if (!outer || !row) return;
    const check = () => setCollapsed(row.scrollWidth > outer.clientWidth + 1);
    check();
    if (typeof ResizeObserver === "undefined") return;
    const watch = new ResizeObserver(check);
    watch.observe(outer);
    return () => watch.disconnect();
  }, [shown.length]);
  if (shown.length < 2) return null;   // one choice is no choice
  const name = (s: Segment<T>) => (s.count === undefined ? s.text : `${s.text}, ${s.count}`);
  const row = (measuring: boolean) => shown.map((s) => (
    <button key={s.id} type="button" className="lm-seg__item" aria-pressed={s.id === value}
            tabIndex={measuring ? -1 : undefined} aria-label={measuring ? undefined : name(s)}
            onClick={measuring ? undefined : () => onChange(s.id)}>
      {s.label}
      {s.count !== undefined ? <span className="lm-seg__n" aria-hidden="true">{s.count}</span> : null}
    </button>
  ));
  return (
    <div className="lm-seg" ref={box}>
      {/* the full row, laid out but invisible, so the fit is measured at every width */}
      <div className="lm-seg__measurebox" aria-hidden="true" inert>
        <div className="lm-seg__row lm-seg__measure" ref={measure}>{row(true)}</div>
      </div>
      {collapsed ? (
        <label className="lm-seg__select">
          <span className="lm-seg__selectlabel">{label}</span>
          <select value={shown.some((s) => s.id === value) ? value : ""}
                  onChange={(event) => onChange(event.target.value as T)}>
            {shown.some((s) => s.id === value) ? null : <option value="" disabled>{label}</option>}
            {shown.map((s) => <option key={s.id} value={s.id}>{s.count === undefined ? s.text : `${s.text} (${s.count})`}</option>)}
          </select>
        </label>
      ) : (
        <div className="lm-seg__row" role="group" aria-label={label}>{row(false)}</div>
      )}
    </div>
  );
}
