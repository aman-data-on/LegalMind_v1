/** QA-027: after sign-in the reader returns to the page they were on — and only ever
 *  to a page on this site, so ?next= cannot send them to another origin. */
import { expect, it } from "vitest";

import { safeNext } from "@/lib/session";

it("returns to a path on this site, and to the dashboard otherwise", () => {
  expect(safeNext("/dashboard/contracts/abc?tab=findings")).toBe("/dashboard/contracts/abc?tab=findings");
  for (const bad of [null, "", "https://evil.example", "//evil.example", "/\\evil.example", "javascript:alert(1)"]) {
    expect(safeNext(bad)).toBe("/dashboard");
  }
});

it("forgets one person's highlights and choices at sign-out, and keeps view settings", async () => {
  const { forgetPersonalNotes } = await import("@/lib/session");
  const store = new Map<string, string>([
    ["legalmind.annotations.v1", "[]"], ["diff-talk:choices:v2:a|b", "{}"],
    ["legalmind.workspace.zoom", "1.2"], ["legalmind.shortcuts.off", "1"]]);
  const localStorage = {
    get length() { return store.size; },
    key: (i: number) => [...store.keys()][i] ?? null,
    removeItem: (k: string) => void store.delete(k),
  };
  const g = globalThis as { window?: unknown };
  const before = g.window;
  g.window = { localStorage };
  try {
    forgetPersonalNotes();
  } finally {
    g.window = before;
  }
  expect([...store.keys()].sort()).toEqual(["legalmind.shortcuts.off", "legalmind.workspace.zoom"]);
});
