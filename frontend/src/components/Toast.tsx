"use client";

/**
 * Toasts (UX Batch 2). Two uses, nothing else:
 *  - `toast("Sent to Legal")` confirms the reader's own action: bottom centre, one line,
 *    gone after 5 s, paused while hovered or focused (Carbon);
 *  - `toastFailure("Departments could not be loaded")` reports a BACKGROUND failure that has
 *    no region of its own — the replacement for `.catch(() => undefined)`. It stays until
 *    dismissed (WCAG 2.2.1) and is announced as an alert.
 * A failure inside a region the reader is looking at stays inline (`ErrorState`); a toast
 * is never the only record of something the reader must act on.
 *
 * A module-level store, so a `.catch` anywhere can report without a provider in its tree;
 * `<Toaster />` is mounted once, in the root layout.
 */

import { useEffect, useRef, useState, useSyncExternalStore } from "react";

import { describeError } from "@/lib/api";
import { FEEDBACK_COPY } from "@/lib/labels";
import { IconAlertCircle, IconCheckCircle, IconX } from "@/components/workspace/icons";

type Item = { id: number; title: string; body?: string | undefined; failure: boolean };

let items: Item[] = [];
let next = 1;
const listeners = new Set<() => void>();
const emit = () => { for (const listen of listeners) listen(); };
const subscribe = (listen: () => void) => { listeners.add(listen); return () => { listeners.delete(listen); }; };
const snapshot = () => items;
const none: Item[] = [];

export function dismissToast(id: number): void {
  items = items.filter((t) => t.id !== id);
  emit();
}

/** Confirm the reader's own action ("Sent to Legal"). */
export function toast(title: string): void {
  items = [...items, { id: next++, title, failure: false }].slice(-3);
  emit();
}

/** A `.catch` handler for a background failure: `promise.catch(toastFailure("…"))`. */
export function toastFailure(title: string): (cause: unknown) => void {
  return (cause) => {
    items = [...items, { id: next++, title, body: describeError(cause), failure: true }].slice(-3);
    emit();
  };
}

const LIFE_MS = 5000;

function One({ item }: { item: Item }) {
  const [held, setHeld] = useState(false);
  const left = useRef(LIFE_MS);
  useEffect(() => {
    if (item.failure || held) return;
    const started = Date.now();
    const timer = window.setTimeout(() => dismissToast(item.id), left.current);
    return () => { window.clearTimeout(timer); left.current -= Date.now() - started; };
  }, [item, held]);
  return (
    <div className={`lm-toast${item.failure ? " lm-toast--failure" : ""}`} role={item.failure ? "alert" : undefined}
         onMouseEnter={() => setHeld(true)} onMouseLeave={() => setHeld(false)}
         onFocus={() => setHeld(true)} onBlur={() => setHeld(false)}>
      <span className="lm-toast__icon">{item.failure ? <IconAlertCircle size={16} /> : <IconCheckCircle size={16} />}</span>
      <p className="lm-toast__text">
        <span className="lm-toast__title">{item.title}</span>
        {item.body ? <span className="lm-toast__body">{item.body}</span> : null}
      </p>
      <button type="button" className="lm-toast__close" aria-label={FEEDBACK_COPY.dismiss}
              onClick={() => dismissToast(item.id)}>
        <IconX size={16} />
      </button>
    </div>
  );
}

export function Toaster() {
  const list = useSyncExternalStore(subscribe, snapshot, () => none);
  // always mounted: a live region present before its text arrives is announced reliably
  return (
    <div className="lm-toaster" aria-live="polite">
      {list.map((item) => <One key={item.id} item={item} />)}
    </div>
  );
}
