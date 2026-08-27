/**
 * The "?" shortcuts help — Phase 4 hardening.
 *
 * Pins the two safety properties of the shortcut system's public face: the help
 * renders from the same table the handlers use (so it cannot describe bindings
 * that don't exist), and it says in plain text that no key records a decision.
 * The bindings themselves are interaction and belong to the Playwright suite
 * (e2e/keyboard.spec.ts), per the house split.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { KeyboardShortcutsHelp } from "@/components/KeyboardShortcuts";
import { REVIEW_SHORTCUTS } from "@/lib/shortcuts";

describe("KeyboardShortcutsHelp", () => {
  it("renders nothing while closed", () => {
    expect(
      renderToStaticMarkup(<KeyboardShortcutsHelp open={false} onClose={() => {}} />),
    ).toBe("");
  });

  it("is a labelled dialog listing every binding from the single source", () => {
    const html = renderToStaticMarkup(
      <KeyboardShortcutsHelp open onClose={() => {}} />,
    );
    expect(html).toContain('role="dialog"');
    expect(html).toContain('aria-modal="true"');
    for (const shortcut of REVIEW_SHORTCUTS) {
      expect(html).toContain(`<kbd>${shortcut.key}</kbd>`);
    }
  });

  it("states that no shortcut records a decision", () => {
    const html = renderToStaticMarkup(
      <KeyboardShortcutsHelp open onClose={() => {}} />,
    );
    expect(html).toContain("none of them records a decision");
  });

  it("the a/r bindings are described as preparing, never submitting", () => {
    const accept = REVIEW_SHORTCUTS.find((s) => s.key === "a");
    const reject = REVIEW_SHORTCUTS.find((s) => s.key === "r");
    expect(accept?.does).toContain("never submits");
    expect(reject?.does).toContain("never submits");
  });
});
