/**
 * UX Batch 2 — the design foundation stays one foundation. These fail the build when a
 * stylesheet reaches past the tokens again (the class of failure that produced 18 font
 * sizes and 296 nodes under 12px), and pin the shared states' contracts (GP-3, GP-4).
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { EmptyState, ErrorBanner, ErrorState, LoadingState, NoticeState } from "@/components/Feedback";
import { SegmentedFilter } from "@/components/SegmentedFilter";
import { StatusChip, chipStatus } from "@/components/StatusChip";
import { ApiError } from "@/lib/api";

function cssFiles(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry);
    if (statSync(path).isDirectory()) cssFiles(path, out);
    else if (path.endsWith(".css") && !path.endsWith("fonts.css")) out.push(path);
  }
  return out;
}
const declarations = (re: RegExp) => cssFiles("src").flatMap((file) =>
  [...readFileSync(file, "utf8").matchAll(re)].map((m) => `${file}: ${m[0]}`));

describe("one type scale, through tokens only", () => {
  it("sets no literal font size anywhere in the CSS", () => {
    // a size is a token (var(--t-*) or an alias); `inherit`, 1em and the zoom calc stay legal
    const literal = declarations(/font-size:(?!\s*(?:var\(|inherit|1em\b|0\b|calc\(var\())\s*[^;}]+/g);
    expect(literal).toEqual([]);
  });

  it("declares the scale once: 24 / 18 / 16 / 15 / 14 / 13 / 12, and 17 for contract text", () => {
    const root = readFileSync("src/app/globals.css", "utf8");
    for (const [token, rem] of [["--t-page", "1.5rem"], ["--t-section", "1.125rem"], ["--t-subsection", "1rem"],
      ["--t-body", "0.9375rem"], ["--t-dense", "0.875rem"], ["--t-caption", "0.8125rem"],
      ["--t-label", "0.75rem"], ["--t-legal", "1.0625rem"]] as const) {
      expect(root).toContain(`${token}: ${rem};`);
    }
  });

  it("uses only the loaded weights, and no uppercase or tracked labels", () => {
    expect(declarations(/font-weight:\s*(450|550|650)\b/g)).toEqual([]);
    expect(declarations(/text-transform:\s*uppercase/g)).toEqual([]);
    // round 2: tracking was for capitals; on sentence case it reads as stretched type
    expect(declarations(/letter-spacing:\s*0?\.\d+/g)).toEqual([]);
  });

  it("never aliases the old small tokens down (round 2): rows read at 14, metadata at 13", () => {
    const ws = readFileSync("src/app/dashboard/workspace.css", "utf8");
    expect(ws).toMatch(/--ws-text-sm: var\(--t-dense\);/);
    expect(ws).toMatch(/--ws-text-xs: var\(--t-caption\);/);
  });
});

describe("the shared states (GP-3, GP-4)", () => {
  const noId = new ApiError(500, "INTERNAL", "The request failed.", "-");
  const withId = new ApiError(500, "INTERNAL", "The request failed.", "7F3A21");

  it("never prints a reference without one, and words it for support when there is one", () => {
    const bare = renderToStaticMarkup(<ErrorState title="Standards could not be loaded" error={noId} onRetry={() => {}} />);
    expect(bare).not.toMatch(/Reference|reference/);
    expect(bare).toContain("Standards could not be loaded");
    expect(bare).toContain("Try again");
    expect(bare).toContain("Check your connection and try again.");
    expect(renderToStaticMarkup(<ErrorState title="X" error={withId} />)).toContain("Error reference for support: 7F3A21");
    expect(renderToStaticMarkup(<ErrorBanner error={noId} />)).not.toContain("Reference");
  });

  it("does not tell a reader to check their connection when the server explained the refusal", () => {
    const gone = new ApiError(401, "UNAUTHENTICATED", "Sign in.", "-");
    const html = renderToStaticMarkup(<ErrorState title="Your to-do could not be loaded" error={gone} />);
    expect(html).toContain("Your session has ended. Sign in again.");
    expect(html).not.toContain("connection");
  });

  it("announces loading politely, and empty says what is true and what to do", () => {
    expect(renderToStaticMarkup(<LoadingState label="Loading standards…" rows={3} />))
      .toMatch(/role="status" aria-live="polite"[\s\S]*Loading standards…[\s\S]*lm-skel__row/);
    const empty = renderToStaticMarkup(<EmptyState title="No changes from the client" body="You can prepare the final contract." />);
    expect(empty).toContain("No changes from the client");
    expect(empty).toContain("You can prepare the final contract.");
  });
});

describe("the one status chip", () => {
  it("maps the server's reader words to the fixed words, and favour only on the server's flag", () => {
    expect(chipStatus("ACCEPTABLE")).toBe("MATCHES");
    expect(chipStatus("REQUIRES_MODIFICATION")).toBe("CHANGE_NEEDED");
    expect(chipStatus("MISSING")).toBe("MISSING");
    expect(chipStatus("NEEDS_DECISION")).toBe("NEEDS_DECISION");
    expect(chipStatus("REQUIRES_MODIFICATION", true)).toBe("IN_OUR_FAVOUR");
  });

  it("is word + icon + tone, and a decided point keeps its status (RESOLVED ≠ MATCH)", () => {
    const missing = renderToStaticMarkup(<StatusChip status="MISSING" />);
    expect(missing).toMatch(/lm-chip--missing[\s\S]*lucide-file-plus[\s\S]*Missing/);
    const decided = renderToStaticMarkup(<StatusChip status="CHANGE_NEEDED" decided="We accepted their wording" />);
    expect(decided).toContain("Change needed");
    expect(decided).toContain("Decided: We accepted their wording");
    expect(decided).not.toContain("Matches");
  });
});

describe("round 2 components", () => {
  it("a filter offers no zero-count choice, and one choice is no control at all", () => {
    const html = renderToStaticMarkup(<SegmentedFilter label="Show" value="all" onChange={() => {}} segments={[
      { id: "all", label: "All", text: "All", count: 3, always: true },
      { id: "a", label: "Change needed", text: "Change needed", count: 3 },
      { id: "b", label: "Missing", text: "Missing", count: 0 },
    ]} />);
    expect(html).toContain('role="group" aria-label="Show"');
    expect(html).not.toContain("Missing");
    expect(html).not.toMatch(/lm-chip|border-radius: 999/);
    expect(renderToStaticMarkup(<SegmentedFilter label="Show" value="all" onChange={() => {}}
      segments={[{ id: "all", label: "All", text: "All", count: 0, always: true }]} />)).toBe("");
  });

  it("a question is a notice, never an alert or an error", () => {
    const html = renderToStaticMarkup(<NoticeState title="Whose paper is this version?" />);
    expect(html).toContain("lm-state--notice");
    expect(html).not.toMatch(/role="alert"|lm-state--error|reference/i);
  });

  it("a server failure says the fix, never the server's raw word", () => {
    const html = renderToStaticMarkup(<ErrorState title="Contracts could not be loaded"
      error={new ApiError(500, "INTERNAL", "Internal error", "-")} onRetry={() => {}} />);
    expect(html).not.toContain("Internal error");
    expect(html).toContain("Check your connection and try again.");
  });
});
