/**
 * Workspace slice 1 — the pure model and the honest placeholders.
 *
 * Static assertions in the house idiom; the highlight gesture, collapse tabs and
 * real data live in e2e/workspace.spec.ts against the real backend.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { NextSlice } from "@/components/workspace/NextSlice";
import {
  groupByPage,
  locationLabel,
  navItemsFor,
  outlineOf,
  readiness,
} from "@/components/workspace/model";
import * as P from "@/lib/permissions";
import type { EvidenceRow } from "@/lib/types";

function row(overrides: Partial<EvidenceRow>): EvidenceRow {
  return {
    id: "e",
    document_version_id: "v",
    page_number: 1,
    section_number: null,
    section_title: null,
    content: "text",
    source_type: "NATIVE",
    start_offset: 0,
    end_offset: 4,
    ...overrides,
  };
}

describe("readiness from counts", () => {
  it("derives the three plain states and never invents a fourth", () => {
    expect(readiness(undefined)).toBe("not-indexed");
    expect(readiness({ chunks: 0, embedded_chunks: 0 })).toBe("not-indexed");
    expect(readiness({ chunks: 12, embedded_chunks: 0 })).toBe("lexical-only");
    expect(readiness({ chunks: 12, embedded_chunks: 12 })).toBe("ready");
  });
});

describe("reading order", () => {
  it("groups consecutive rows by page and keeps unnumbered rows as their own group", () => {
    const groups = groupByPage([
      row({ id: "a", page_number: 1 }),
      row({ id: "b", page_number: 1 }),
      row({ id: "c", page_number: 2 }),
      row({ id: "d", page_number: null }),
    ]);
    expect(groups.map((g) => [g.page, g.rows.length])).toEqual([[1, 2], [2, 1], [null, 1]]);
  });

  it("the outline is exactly the rows that carry a clause reference", () => {
    const rows = [
      row({ id: "a", section_number: "17.2" }),
      row({ id: "b" }),
      row({ id: "c", section_title: "Definitions" }),
    ];
    expect(outlineOf(rows).map((r) => r.id)).toEqual(["a", "c"]);
  });

  it("labels a location from whatever the parser recorded", () => {
    expect(locationLabel(row({ section_number: "17.2", section_title: "Liability", page_number: 9 })))
      .toBe("§17.2 · Liability · p.9");
    expect(locationLabel(row({ page_number: null }))).toBe("location not recorded");
  });
});

describe("navigation by absence (52.3)", () => {
  it("an ordinary user sees Documents and Reviews, never Legal or Admin", () => {
    const user = new Set([P.CONTRACT_VIEW, P.REVIEW_VIEW, P.ASSIST_ASK]);
    expect(navItemsFor((p) => user.has(p)).map((i) => i.label)).toEqual(["Documents", "Reviews"]);
  });

  it("a super admin sees only the control plane — no Documents at all", () => {
    const admin = new Set([P.AUDIT_VIEW, P.USER_MANAGE]);
    expect(navItemsFor((p) => admin.has(p)).map((i) => i.label)).toEqual(["Audit", "Admin"]);
  });
});

describe("NextSlice", () => {
  it("names the pane, says it is not built, points at today's route — and renders no control", () => {
    const html = renderToStaticMarkup(
      <NextSlice title="Findings" todayHref="/reviews" todayLabel="findings are on the Reviews screen" />,
    );
    expect(html).toContain("Findings");
    expect(html).toContain("next build slice");
    expect(html).toContain('href="/reviews"');
    expect(html).not.toContain("<button");
    expect(html).not.toContain("<input");
  });
});
