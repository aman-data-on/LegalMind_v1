/**
 * W2-1: `workspace.css` is no longer in the root layout, so every signed-in section must pull it
 * itself — the dashboard layout imports it, and each other top-level section re-uses that layout.
 * The root 404 and error pages bring it through their own dynamic import. A new section that
 * forgets would render unstyled; this test names it.
 */
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const APP = join(__dirname, "..", "app");
const read = (...p: string[]) => readFileSync(join(APP, ...p), "utf8");
// sections that render outside the workspace shell on purpose
const OUTSIDE = ["login"];

describe("every signed-in section loads workspace.css", () => {
  it("the dashboard layout imports it", () => {
    expect(read("dashboard", "layout.tsx")).toMatch(/import "\.\/workspace\.css";/);
  });

  const sections = readdirSync(APP).filter((d) => statSync(join(APP, d)).isDirectory()
    && !OUTSIDE.includes(d) && d !== "dashboard" && existsSync(join(APP, d, "layout.tsx")));
  it.each(sections)("/%s re-uses the dashboard layout", (d) => {
    expect(read(d, "layout.tsx")).toMatch(/from "\.\.\/dashboard\/layout"/);
  });

  it("every top-level section has a layout (or is listed as outside the shell)", () => {
    const bare = readdirSync(APP).filter((d) => statSync(join(APP, d)).isDirectory()
      && !OUTSIDE.includes(d) && !existsSync(join(APP, d, "layout.tsx")));
    expect(bare).toEqual([]);
  });

  it("the root 404 and error pages bring it themselves", () => {
    expect(read("notFoundBody.tsx")).toMatch(/import "\.\/dashboard\/workspace\.css";/);
    expect(read("workspaceSheetBody.tsx")).toMatch(/import "\.\/dashboard\/workspace\.css";/);
    expect(read("error.tsx")).toMatch(/import\("\.\/workspaceSheetBody"\)/);
    expect(read("layout.tsx")).not.toMatch(/workspace\.css/);
  });
});
