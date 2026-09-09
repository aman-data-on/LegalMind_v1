/**
 * Keyboard shortcut plumbing — Phase 4 hardening (2026-08-27).
 *
 * One shared rule and one shared table, so the page handler and the per-panel
 * handler cannot drift apart.
 *
 * The rule: **a single-key shortcut never fires while the user is typing.** A
 * reviewer writing a justification that contains the letter "a" must not have the
 * decision type silently changed under them. Modifier chords are also left alone —
 * the browser owns those.
 */

export function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  const tag = target.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
}

export function shortcutKey(event: KeyboardEvent): string | null {
  if (event.metaKey || event.ctrlKey || event.altKey) return null;
  if (isTypingTarget(event.target)) return null;
  return event.key;
}

/**
 * The single source for the help overlay ("?") and for the specs that assert the
 * bindings exist. "a"/"r" deliberately read "prepare", not "record": a single
 * keystroke never completes a Legal Decision — it preselects the type and moves
 * focus to the mandatory justification field, and only an explicit submit records
 * anything (Step 31 r11; 52.7's no-optimistic-UI posture applied to input as well
 * as output).
 */
export const REVIEW_SHORTCUTS: ReadonlyArray<{ key: string; does: string }> = [
  // Navigation, on the bindings a reviewer already knows from other tools
  // (2026-09-04): j/k as in Gmail and GitHub, with this product's original n/p
  // kept as aliases so nobody's habit breaks.
  { key: "j  or  n", does: "Next finding" },
  { key: "k  or  p", does: "Previous finding" },
  { key: "/", does: "Find in the document" },
  // Decision keys. Owned by the decision form itself, and deliberately named
  // "prepare": a single keystroke never records a Legal Decision (Step 31 r11).
  { key: "d", does: "Jump to the decision form for the focused finding" },
  { key: "a", does: "Prepare ACCEPT_DEVIATION — selects it and focuses the justification (never submits)" },
  { key: "r", does: "Prepare REJECT — selects it and focuses the justification (never submits)" },
  { key: "?", does: "Show or hide this list" },
  { key: "Esc", does: "Close this list, or the Ask panel" },
];
