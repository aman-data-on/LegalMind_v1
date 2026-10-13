import { useCallback, useEffect, useEffectEvent, useRef, useState } from "react";

/**
 * Where the reader is in a review, and how they move: Previous / Next, J / K, a
 * click in the changes list, or plain scrolling (the list follows the reading).
 *
 * - `announcement` is what a screen reader hears. It changes only when the reader
 *   MOVES (or makes a choice) — never on plain scrolling, which would make the
 *   counter chatter (strict review, 2026-10-13).
 * - A jump the reader asked for wins until the reader scrolls: the jump's own
 *   scroll reports, or a last difference the page cannot bring to the top, must
 *   not move "current" back (the timed guard did, at the end of a list).
 */
const SCROLL_KEYS = new Set([" ", "PageDown", "PageUp", "ArrowDown", "ArrowUp", "Home", "End"]);

export function useReviewNavigation({ order, label, ready, watch }: {
  /** Row indices the reader steps through, in order (the current filter). */
  order: number[];
  /** How a row is named aloud ("1. Definitions"). */
  label: (row: number) => string;
  ready: boolean;
  /** Re-observe the cards when what is shown changes. */
  watch: unknown[];
}) {
  const [current, setCurrent] = useState(-1);
  const [announcement, setAnnouncement] = useState("");
  /** The reader has scrolled since the last jump — only then does reading move "current". */
  const scrolled = useRef(true);
  /** The cards, by row index — owned here, registered by the review. */
  const cards = useRef<(HTMLElement | null)[]>([]);
  const registerCard = useCallback((row: number) => (el: HTMLElement | null) => {
    cards.current[row] = el;
  }, []);

  const show = useCallback((target: number) => {
    scrolled.current = false;
    setCurrent(target);
    setAnnouncement(`Difference ${order.indexOf(target) + 1} of ${order.length}: ${label(target)}`);
    // The card stops clear of what is pinned: its `scroll-margin-top` reads the
    // pinned heights the page publishes as CSS variables.
    const el = cards.current[target];
    el?.scrollIntoView({ block: "start" });
    el?.focus({ preventScroll: true });
  }, [order, label]);

  const go = useCallback((step: 1 | -1) => {
    if (!order.length) return;
    const at = order.indexOf(current);
    const next = at === -1 ? (step === 1 ? 0 : order.length - 1)
      : (at + step + order.length) % order.length;
    show(order[next] ?? 0);
  }, [order, current, show]);

  // J / K — next / previous, as in mail and code review; never while typing or
  // while a control (a radio, a select) has focus.
  const onKey = useEffectEvent((e: KeyboardEvent) => {
    const t = e.target as HTMLElement;
    if (e.metaKey || e.ctrlKey || e.altKey || /^(INPUT|SELECT|TEXTAREA)$/.test(t.tagName)
        || t.isContentEditable || t.closest("dialog")) return;   // not behind the open sheet
    if (e.key === "j") go(1);
    if (e.key === "k") go(-1);
  });
  useEffect(() => {
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // The changes list follows the reading: the card in the upper third is current.
  const onSeen = useEffectEvent((entries: IntersectionObserverEntry[]) => {
    if (!scrolled.current) return;
    const top = entries.filter((e) => e.isIntersecting)
      .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
    if (top) setCurrent(Number((top.target as HTMLElement).dataset.row));
  });
  useEffect(() => {
    // What a reader scrolls with: wheel, touch, keys (Space, Page Down, arrows) and
    // the scrollbar (a pointer press). J / K themselves jump again.
    const moved = (e: Event) => {
      if (!(e instanceof KeyboardEvent) || SCROLL_KEYS.has(e.key)) scrolled.current = true;
    };
    const events = ["wheel", "touchmove", "pointerdown", "keydown"] as const;
    events.forEach((t) => window.addEventListener(t, moved, { passive: true }));
    return () => events.forEach((t) => window.removeEventListener(t, moved));
  }, []);
  useEffect(() => {
    if (!ready) return;
    const io = new IntersectionObserver(onSeen, { rootMargin: "-30% 0px -60% 0px" });
    cards.current.forEach((el) => el && io.observe(el));
    return () => io.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `watch` lists what re-renders the cards
  }, [ready, ...watch]);

  return { current, show, go, announcement, setAnnouncement, registerCard };
}
