"use client";

/**
 * The "?" shortcuts help — Phase 4 hardening (2026-08-27).
 *
 * A real dialog, and the one modal use DESIGN.md sanctions ("a genuine
 * interruption"): the user explicitly summoned it, it answers one question, and
 * Escape or the close control dismisses it. Focus moves into the dialog on open
 * and back to where it was on close, so a keyboard user is never stranded.
 *
 * The table renders from `REVIEW_SHORTCUTS`, the same source the page handlers
 * use — the help cannot describe bindings that don't exist.
 */

import { useEffect, useRef } from "react";

import { REVIEW_SHORTCUTS } from "@/lib/shortcuts";

export function KeyboardShortcutsHelp({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const restoreRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    restoreRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    dialogRef.current?.focus();
    return () => restoreRef.current?.focus();
  }, [open]);

  if (!open) return null;

  return (
    <div
      className="shortcuts-overlay"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={dialogRef}
        className="shortcuts-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="shortcuts-title"
        tabIndex={-1}
        onKeyDown={(event) => {
          if (event.key === "Escape") onClose();
          /* While the dialog holds focus, page- and panel-level single-key
             handlers must not also fire. */
          event.stopPropagation();
        }}
      >
        <h2 id="shortcuts-title">Keyboard shortcuts</h2>
        <table>
          <tbody>
            {REVIEW_SHORTCUTS.map((shortcut) => (
              <tr key={shortcut.key}>
                <th scope="row">
                  <kbd>{shortcut.key}</kbd>
                </th>
                <td>{shortcut.does}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="hint">
          Shortcuts never fire while you are typing in a field, and none of them
          records a decision — only the Record decision button does that.
        </p>
        <button type="button" className="btn btn--secondary" onClick={onClose}>
          Close
        </button>
      </div>
    </div>
  );
}
