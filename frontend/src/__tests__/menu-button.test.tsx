/**
 * M3 r2: the shared menu button (WAI-ARIA APG "Menu Button") and the check on a chosen view.
 * Static render plus the roving-tabindex helper; the keys themselves are pinned in the browser.
 */
import { readFileSync } from "node:fs";
import postcss from "postcss";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { MenuButton, focusAt } from "@/components/MenuButton";

describe("MenuButton", () => {
  it("is a closed menu button named by its label, ⋯ unless given another glyph", () => {
    const html = renderToStaticMarkup(<MenuButton label="More actions"><button role="menuitem">A</button></MenuButton>);
    expect(html).toContain('aria-haspopup="menu"');
    expect(html).toContain('aria-expanded="false"');
    expect(html).toContain('aria-label="More actions"');
    expect(html).toContain("⋯");
    expect(html).not.toContain('role="menu"');
    const other = renderToStaticMarkup(<MenuButton label="Document options" icon={<svg />}>{null}</MenuButton>);
    expect(other).not.toContain("⋯");
    expect(other).toContain('title="Document options"');
  });

  it("keeps one item in the tab order and wraps at both ends", () => {
    const made = () => { const el = { tabIndex: 0, focused: false, focus() { this.focused = true; } }; return el; };
    const items = [made(), made(), made()];
    const list = { querySelectorAll: () => items } as unknown as HTMLElement;
    focusAt(list, -1);
    expect(items.map((i) => i.tabIndex)).toEqual([-1, -1, 0]);
    expect(items[2]!.focused).toBe(true);
    focusAt(list, 3);
    expect(items.map((i) => i.tabIndex)).toEqual([0, -1, -1]);
    expect(() => focusAt(null, 0)).not.toThrow();
  });

  it("marks a chosen radio item as well as a pressed checkbox item", () => {
    const css = "src/app/dashboard/workspace.css";
    const selectors: string[] = [];
    postcss.parse(readFileSync(css, "utf8"), { from: css }).walkRules((r) => { selectors.push(r.selector); });
    const check = selectors.find((s) => s.includes("menuitemradio") && s.includes('[aria-checked="true"]::after'));
    expect(check).toBeDefined();
    expect(check).toContain("menuitemcheckbox");
  });
});
