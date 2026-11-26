"use client";

import { useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";

const ITEMS = '[role="menuitem"], [role="menuitemradio"], [role="menuitemcheckbox"]';
const itemsIn = (list: HTMLElement | null) => [...(list?.querySelectorAll<HTMLElement>(ITEMS) ?? [])];
/** Roving tabindex: only the focused item is in the tab order; the index wraps. */
export function focusAt(list: HTMLElement | null, index: number) {
  const all = itemsIn(list);
  if (!all.length) return;
  const at = (index + all.length) % all.length;
  all.forEach((el, i) => { el.tabIndex = i === at ? 0 : -1; });
  all[at]!.focus();
}

/**
 * A WAI-ARIA menu button (APG "Menu Button"): the toggle opens a `role="menu"` list and focus
 * moves to its first item; ArrowUp/ArrowDown move (wrapping), Home/End jump, one item is in
 * the tab order at a time (roving tabindex); Escape and Tab close it, Escape returns focus to
 * the toggle; choosing an item closes it. Items are the caller's `role="menuitem*"` buttons.
 *
 * Moved out of the clients page (M3 r2) so the workspace header and the document toolbar use
 * the same control. On a phone workspace the list is a sheet above the tab bar (workspace.css).
 */
export function MenuButton({ children, label, icon, title }: {
  children: ReactNode;
  /** the toggle's accessible name (it shows ⋯ or `icon`) */
  label: string;
  /** a different glyph, for a second menu beside a ⋯ */
  icon?: ReactNode;
  /** a visible heading for the list (the phone sheet) — it names the menu */
  title?: string;
}) {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const toggleRef = useRef<HTMLButtonElement | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);
  const titleId = useId();

  const items = () => itemsIn(listRef.current);
  const focusItem = (index: number) => focusAt(listRef.current, index);

  useEffect(() => {
    if (!open) return;
    focusAt(listRef.current, 0);
    function onPointer(event: PointerEvent) {
      if (!wrapRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("pointerdown", onPointer);
    return () => document.removeEventListener("pointerdown", onPointer);
  }, [open]);

  function onKey(event: KeyboardEvent<HTMLDivElement>) {
    const all = items();
    const now = all.indexOf(document.activeElement as HTMLElement);
    const move: Record<string, number> = { ArrowDown: now + 1, ArrowUp: now - 1, Home: 0, End: all.length - 1 };
    if (event.key in move) {
      event.preventDefault();
      focusItem(move[event.key]!);
    } else if (event.key === "Escape") {
      // the shell's single-key shortcuts never see it; focus goes back to the toggle
      event.preventDefault();
      event.stopPropagation();
      setOpen(false);
      toggleRef.current?.focus();
    } else if (event.key === "Tab") {
      setOpen(false);
    }
  }

  return (
    <div className="ws-menu ws-cl__headmenu" ref={wrapRef}>
      <button ref={toggleRef} type="button"
              className="ws-btn ws-btn--sm ws-menu__toggle"
              aria-haspopup="menu" aria-expanded={open} aria-label={label} title={icon ? label : undefined}
              onClick={() => setOpen((was) => !was)}>
        {icon ?? "⋯"}
      </button>
      {open ? (
        <div className="ws-menu__list" role="menu" aria-orientation="vertical" ref={listRef}
             aria-labelledby={title ? titleId : undefined} aria-label={title ? undefined : label}
             onKeyDown={onKey}
             onClick={(event) => {
               if ((event.target as HTMLElement).closest(ITEMS)) { setOpen(false); toggleRef.current?.focus(); }
             }}>
          {title ? <p id={titleId} className="ws-menu__title">{title}</p> : null}
          {children}
        </div>
      ) : null}
    </div>
  );
}
