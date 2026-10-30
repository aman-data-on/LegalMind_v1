/** QA-026 (WCAG 2.1.4): single-key shortcuts can be turned off, and the button that
 *  opens the sheet to turn them back on still works. */
import { afterEach, beforeEach, expect, it, vi } from "vitest";

import { setShortcutsOff, shortcutKey } from "@/lib/shortcuts";

afterEach(() => vi.unstubAllGlobals());
// no DOM in this suite: nothing is a typing target
beforeEach(() => vi.stubGlobal("HTMLElement", class {}));

const key = (isTrusted: boolean) =>
  ({ key: "a", isTrusted, target: null, metaKey: false, ctrlKey: false, altKey: false }) as unknown as KeyboardEvent;

it("turns every single-key shortcut off for this reader, and back on", () => {
  const store = new Map<string, string>();
  vi.stubGlobal("window", { localStorage: {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
    removeItem: (k: string) => void store.delete(k) } });
  expect(shortcutKey(key(true))).toBe("a");
  setShortcutsOff(true);
  expect(shortcutKey(key(true))).toBeNull();
  expect(shortcutKey(key(false))).toBe("a");          // the "?" button's own event
  setShortcutsOff(false);
  expect(shortcutKey(key(true))).toBe("a");
});

it("reads as on when storage is unavailable", () => {
  vi.stubGlobal("window", {});
  expect(shortcutKey(key(true))).toBe("a");
});
