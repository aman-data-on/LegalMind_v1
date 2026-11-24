import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/** W1-1: every link prefetches on intent only, through `AppLink`. CI's eslint covers Diff-Talk
 *  alone, so the one-wrapper rule is pinned here too. */
function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? (name === "__tests__" ? [] : files(path)) : /\.tsx?$/.test(name) ? [path] : [];
  });
}

describe("next/link is imported only by AppLink (W1-1)", () => {
  it("no other source file imports it", () => {
    const offenders = files("src").filter((f) => !f.endsWith("components/AppLink.tsx"))
      .filter((f) => /from\s+["']next\/link["']/.test(readFileSync(f, "utf8")));
    expect(offenders).toEqual([]);
  });
});
