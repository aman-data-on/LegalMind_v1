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
  { key: "n", does: "Next finding in the current view" },
  { key: "p", does: "Previous finding in the current view" },
  { key: "d", does: "Jump to the decision form for the current finding" },
  { key: "a", does: "Prepare ACCEPT_DEVIATION — select it and focus the justification (never submits)" },
  { key: "r", does: "Prepare REJECT — select it and focus the justification (never submits)" },
  { key: "?", does: "Show or hide this help" },
];
