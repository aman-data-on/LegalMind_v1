"use client";

/**
 * Workspace keyboard shortcuts — 2026-09-04, owner-approved.
 *
 * The shortcut layer previously existed only in the legacy Review screen, so
 * retiring those routes would have removed a real accessibility affordance
 * rather than dead code. Rebuilt here on the conventions a reviewer already
 * knows from other professional tools, rather than a bespoke scheme:
 *
 *   ?            show / hide the shortcut sheet          (GitHub, Linear, Gmail)
 *   j / k        next / previous item                    (Gmail, GitHub)
 *   n / p        the same, kept as aliases               (this product's own)
 *   /            focus the find-in-document field        (GitHub, Linear)
 *   Escape       dismiss the thing that is open          (universal)
 *
 * TWO RULES THAT MAKE IT SAFE, both inherited from `lib/shortcuts`:
 *
 *  - **A single key never fires while the user is typing.** A reviewer writing a
 *    justification containing "a" must not have a decision type change under
 *    them, so `shortcutKey` returns null for inputs, textareas, selects and
 *    contenteditable, and for any modifier chord (the browser owns those).
 *  - **A keystroke never completes a legal act.** Navigation moves focus and
 *    nothing else; the decision keys (owned by `DecisionControl`, not this hook)
 *    preselect and focus, and only an explicit submit records anything
 *    (Step 31 r11, and 52.7's no-optimistic-UI posture applied to input).
 *
 * Focus, not `aria-activedescendant`: the finding cards are real focusable
 * elements, so `j`/`k` move the browser's own focus ring. A screen reader then
 * announces the card it lands on with no extra plumbing, and Tab continues from
 * wherever the reader stopped — the behaviour a keyboard user expects.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { shortcutKey } from "@/lib/shortcuts";

/** The item list `j`/`k` walk, in the order they are on screen. */
const CARD_SELECTOR = "article[data-finding-id]";

export interface WorkspaceShortcuts {
  /** Whether the shortcut sheet is open. */
  helpOpen: boolean;
  closeHelp: () => void;
  openHelp: () => void;
}

export function useWorkspaceShortcuts(): WorkspaceShortcuts {
  const [helpOpen, setHelpOpen] = useState(false);
  const helpOpenRef = useRef(false);
  helpOpenRef.current = helpOpen;

  const move = useCallback((direction: 1 | -1) => {
    const cards = Array.from(document.querySelectorAll<HTMLElement>(CARD_SELECTOR));
    if (cards.length === 0) return false;
    // Start from whatever the reader is actually on, so the keys continue from
    // the current position rather than from an index this hook remembers and
    // the DOM has since changed under (a filter change reorders the list).
    const active = document.activeElement;
    const currentIndex = cards.findIndex(
      (card) => card === active || card.contains(active),
    );
    const next =
      currentIndex === -1
        ? direction === 1 ? 0 : cards.length - 1
        : Math.min(Math.max(currentIndex + direction, 0), cards.length - 1);
    const target = cards[next];
    if (!target) return false;
    target.focus({ preventScroll: true });
    target.scrollIntoView({ block: "nearest" });
    return true;
  }, []);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const key = shortcutKey(event);
      if (key === null) return;

      if (key === "?") {
        setHelpOpen((open) => !open);
        event.preventDefault();
        return;
      }
      if (key === "Escape" && helpOpenRef.current) {
        setHelpOpen(false);
        event.preventDefault();
        return;
      }
      // While the sheet is open it owns the keyboard — anything else would move
      // focus underneath a dialog the reader is still reading.
      if (helpOpenRef.current) return;

      if (key === "j" || key === "n") {
        if (move(1)) event.preventDefault();
        return;
      }
      if (key === "k" || key === "p") {
        if (move(-1)) event.preventDefault();
        return;
      }
      if (key === "/") {
        // The document's own find field, which is what "/" means everywhere
        // else. Opening it is the toolbar's job, so this asks for it by click
        // and then focuses whatever input appears.
        const toggle = document.querySelector<HTMLElement>(
          'button[aria-label="Find in document"]',
        );
        if (!toggle) return;
        if (toggle.getAttribute("aria-expanded") !== "true") toggle.click();
        window.setTimeout(() => {
          document.querySelector<HTMLInputElement>(".ws-doccard__find input")?.focus();
        }, 0);
        event.preventDefault();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [move]);

  return {
    helpOpen,
    closeHelp: useCallback(() => setHelpOpen(false), []),
    openHelp: useCallback(() => setHelpOpen(true), []),
  };
}
