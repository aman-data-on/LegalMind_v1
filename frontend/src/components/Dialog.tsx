"use client";

/**
 * Shared modal dialog shell — wraps `@radix-ui/react-dialog` (owner approved
 * shadcn/ui + Tailwind as component foundation, 2026-09-10; this uses Radix
 * directly, without Tailwind or the shadcn CLI, since neither is needed to
 * get its accessibility primitive — see docs/design/SHADCN_ADOPTION_REPORT.md).
 *
 * Replaces five hand-rolled copies (four in `dashboard/page.tsx`, one in
 * `workspace/WorkspacePage.tsx`) that each reimplemented focus-restore and
 * Escape-to-close by hand, with none of them actually trapping focus inside
 * the dialog (Tab could always leave it). Radix's `Dialog.Content` gives a
 * real focus trap for free, on top of the same class names, `role`, and
 * `aria-*` output the CSS and Playwright suites already depend on.
 *
 * `KeyboardShortcutsHelp` deliberately does NOT use this component — it has
 * its own plain implementation (see that file) because its Vitest test
 * asserts on `renderToStaticMarkup` output directly, and Radix's `Portal`
 * renders nothing under Node with no DOM (verified: Portal is the exact
 * failure point, everything else about Radix's Dialog works fine there).
 * That dialog's rendered behaviour is separately covered by
 * `e2e/keyboard.spec.ts` in a real browser, same as this component's six.
 *
 * The Portal target is `.ws`, not the default `document.body` — the exact
 * incident `dashboard/page.tsx`'s row-action menu already hit and fixed
 * (`menuPortalTarget`, 2026-09-03): every design token this CSS uses
 * (`--ws-surface`, `--ws-z-dialog`, `--ws-radius-card`, …) is scoped to `.ws`,
 * not `:root`, specifically so this stylesheet and the legacy one never
 * fight over global tokens. Outside `.ws` those `var(...)` calls have no
 * fallback and resolve to nothing — `background: transparent`,
 * `z-index: auto` — which Playwright's role/text-based assertions do not
 * catch (confirmed: this project's suite passed against that exact bug on
 * the menu until someone opened a real browser). `.ws` sets no
 * transform/filter/contain of its own, so `position: fixed` still resolves
 * against the viewport as this CSS assumes — same reasoning as the menu.
 *
 * `Content` is rendered NESTED inside `Overlay`, not as its sibling (Radix's
 * own examples use siblings, each independently positioned) — because this
 * CSS's `.ws-modal` centres its content via `display:flex;
 * align-items:center; justify-content:center` on the OUTER element, exactly
 * as the original hand-rolled markup nested them. Sibling rendering was tried
 * first and verified broken: the box rendered at `left: 0`, uncentered,
 * because nothing was left to apply that flexbox to. Nesting costs nothing —
 * `Overlay` is an unstyled `Primitive.div` with no behaviour of its own, and
 * Content's own outside-click detection (`DismissableLayer`) still correctly
 * treats a click on the surrounding overlay as "outside Content" by DOM
 * containment, parent or not.
 *
 * `onKeyDown` still calls `stopPropagation()` on every key, not just Escape:
 * `useWorkspaceShortcuts.ts` listens on `window` for single-key navigation
 * (j/k/n/p) and only special-cases the ONE shortcuts-help dialog via a ref
 * check — it does not know about this dialog at all, so without this, "j"
 * pressed while e.g. `CompanyDocuments` is open would still move the finding
 * list underneath it. This does not fight Radix's own Escape/outside-click
 * detection: `@radix-ui/react-use-escape-keydown` and the dismissable-layer's
 * outside-pointer detection both listen on `document` with `capture: true`
 * (verified in `node_modules/@radix-ui/react-use-escape-keydown`), so they
 * run before this bubble-phase handler and are unaffected by it.
 */

import * as RadixDialog from "@radix-ui/react-dialog";
import type { ReactNode } from "react";

export function Dialog({
  onClose,
  titleId,
  dismissOnScrimClick = true,
  children,
}: {
  onClose: () => void;
  /** id of the `<h2>` (or similar) rendered as the first child — every call
      site already renders its own heading with this id, unchanged, so this
      wires `aria-labelledby` to it directly rather than introducing a second,
      Radix-owned title element that would duplicate or reflow that markup. */
  titleId: string;
  /** false for a form dialog where a stray scrim click would discard input
      unrecoverably (`EditContractDialog`). Escape and Cancel remain either way. */
  dismissOnScrimClick?: boolean;
  children: ReactNode;
}) {
  return (
    <RadixDialog.Root open onOpenChange={(open) => { if (!open) onClose(); }}>
      <RadixDialog.Portal container={document.querySelector(".ws") ?? document.body}>
        <RadixDialog.Overlay className="ws-modal">
          <RadixDialog.Content
            className="ws-modal__box"
            aria-labelledby={titleId}
            aria-describedby={undefined}
            onKeyDown={(event) => event.stopPropagation()}
            onInteractOutside={(event) => {
              if (!dismissOnScrimClick) event.preventDefault();
            }}
          >
            {children}
          </RadixDialog.Content>
        </RadixDialog.Overlay>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}
