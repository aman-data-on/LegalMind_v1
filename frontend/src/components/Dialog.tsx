"use client";

/**
 * Shared dialog shell — consolidates six hand-rolled copies (four in
 * `dashboard/page.tsx`, one in `workspace/WorkspacePage.tsx`, one in
 * `KeyboardShortcuts.tsx`) that each reimplemented the same focus-restore +
 * Escape-to-close behaviour. Markup and class names are unchanged so existing
 * CSS and tests (`role="dialog"`, `aria-modal`, `aria-labelledby`) still hold.
 *
 * Deliberately plain divs, not a Radix/shadcn `Dialog`: Step 39 locks Vitest
 * against `renderToStaticMarkup` with a `"node"` test environment and no DOM
 * library (see `vitest.config.ts`) — a portal-based primitive can't render
 * there without adding jsdom, a separate rule-19 dependency decision this
 * consolidation doesn't need. `AskDock`'s non-modal `aria-modal="false"`
 * dialog is a deliberate exception (no focus trap) and is left untouched.
 */

import { useEffect, useRef, type ReactNode } from "react";

export function useDialogFocus(active = true) {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const restoreRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!active) return;
    restoreRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    dialogRef.current?.focus();
    return () => restoreRef.current?.focus();
  }, [active]);

  return dialogRef;
}

export function Dialog({
  onClose,
  titleId,
  overlayClassName = "ws-modal",
  boxClassName = "ws-modal__box",
  dismissOnScrimClick = true,
  children,
}: {
  onClose: () => void;
  titleId: string;
  overlayClassName?: string;
  boxClassName?: string;
  /** false for a form dialog where a stray scrim click would discard input
      unrecoverably (`EditContractDialog`). Escape and Cancel remain either way. */
  dismissOnScrimClick?: boolean;
  children: ReactNode;
}) {
  const dialogRef = useDialogFocus();

  return (
    <div
      className={overlayClassName}
      onClick={
        dismissOnScrimClick
          ? (event) => {
              if (event.target === event.currentTarget) onClose();
            }
          : undefined
      }
    >
      <div
        ref={dialogRef}
        className={boxClassName}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        onKeyDown={(event) => {
          if (event.key === "Escape") onClose();
          event.stopPropagation();
        }}
      >
        {children}
      </div>
    </div>
  );
}
