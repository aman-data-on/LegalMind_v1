"use client";

/**
 * The ONE filter control (UX Batch 2). A filter is not a status, so it never looks like a
 * chip. Two shapes, one behaviour:
 *  - joined (default, 2–4 short options): one row of square-cornered segments;
 *  - `wrap` (5 or more, a narrow pane — Points): separate toggle buttons 8px apart that
 *    wrap onto at most two rows (three in a phone-width pane), so every count stays in view
 *    (re-review R2.3); a select only below 320px.
 * A choice whose count is 0 is not offered (PLAIN-LANGUAGE §5) unless it is selected or
 * `always`. Only when the options cannot fit (one row joined, two rows wrapped) does the
 * control become a native select — the label always above it, never beside it. It never
 * clips or scrolls sideways (WCAG 1.4.10). Presentation only: counts come from the caller.
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

export function SegmentedFilter<T extends string>({ label, segments, value, onChange, wrap = false, showLabel = false }: {
  /** the group's name ("Show changes"), and the select's label when it collapses */
  label: string;
  segments: Segment<T>[];
  value: T;
  onChange: (id: T) => void;
  /** separate buttons on up to two rows (many options in a narrow pane) */
  wrap?: boolean;
  /** show the group's name above the buttons too, not only above a collapsed select */
  showLabel?: boolean;
}) {
  const shown = segments.filter((s) => s.always || s.id === value || s.count === undefined || s.count > 0);
  const box = useRef<HTMLDivElement | null>(null);
  const measure = useRef<HTMLDivElement | null>(null);
  const [collapsed, setCollapsed] = useState(false);
  useLayoutEffect(() => {
    const outer = box.current, row = measure.current;
    if (!outer || !row) return;
    const check = () => {
      if (!wrap) { setCollapsed(row.scrollWidth > outer.clientWidth + 1); return; }
      // wrapped: two rows in a pane (three in a phone-width pane, under 400px, so the counts
      // stay in view); a select only below 320px or when even that would not hold them
      const first = row.firstElementChild as HTMLElement | null;
      const line = first ? first.offsetHeight : 0;
      const rows = outer.clientWidth < 400 ? 3 : 2;
      setCollapsed(outer.clientWidth < 320 || (line > 0 && row.scrollHeight > line * rows + 8 * (rows - 1) + 1));
    };
    check();
    if (typeof ResizeObserver === "undefined") return;
    const watch = new ResizeObserver(check);
    watch.observe(outer);
    return () => watch.disconnect();
  }, [shown.length, wrap]);
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
  const known = shown.some((s) => s.id === value);
  return (
    <div className={`lm-seg${wrap ? " lm-seg--wrap" : ""}`} ref={box}>
      {/* the full set, laid out but invisible and clipped, so the fit is measured at every width */}
      <div className="lm-seg__measurebox" aria-hidden="true" inert>
        <div className="lm-seg__row lm-seg__measure" ref={measure}>{row(true)}</div>
      </div>
      {collapsed ? (
        <label className="lm-seg__select">
          <span className="lm-seg__label">{label}</span>
          <select value={known ? value : ""} onChange={(event) => onChange(event.target.value as T)}>
            {known ? null : <option value="" disabled>{label}</option>}
            {shown.map((s) => <option key={s.id} value={s.id}>{s.count === undefined ? s.text : `${s.text} (${s.count})`}</option>)}
          </select>
        </label>
      ) : (
        <>
          {showLabel ? <p className="lm-seg__label" aria-hidden="true">{label}</p> : null}
          <div className="lm-seg__row" role="group" aria-label={label}>{row(false)}</div>
        </>
      )}
    </div>
  );
}
