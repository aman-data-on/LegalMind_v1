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
