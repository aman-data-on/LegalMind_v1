/**
 * Diff-Talk Setup's lists (review, 2026-10-21): each document is dated by the upload of
 * the version it would compare — with the year — newest first, an unknown date last;
 * client paper and undeclared documents are named as what they are.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/session", () => ({ useSession: () => ({ can: () => true, identity: null }) }));

import { Setup } from "@/components/diff-talk/Setup";
import type { Contract } from "@/lib/types";

const doc = (name: string, source: string | undefined, at: string | null, v = 1) => ({
  id: name, name, contract_type: "MSA", created_at: "2026-01-01T00:00:00Z",
  latest_version: { id: `v-${name}`, version_number: v, processing_status: "COMPLETED",
                    ...(source ? { source } : {}), created_at: at },
}) as unknown as Contract;

const html = renderToStaticMarkup(
  <Setup left="" right="" website={[]} listError={null} onChange={() => {}}
         onUploaded={async () => {}} documents={[
           doc("Old client", "COUNTERPARTY", "2025-10-15T09:00:00Z"),
           doc("New client", "COUNTERPARTY", "2026-10-15T09:00:00Z", 3),
           doc("Undated client", "COUNTERPARTY", null),
           doc("Nobody said", undefined, "2026-10-01T09:00:00Z"),
         ]} />);

describe("Diff-Talk Setup lists", () => {
  it("dates each upload with the year, and names a later version", () => {
    expect(html).toContain("New client (MSA) · 15 Oct 2026 · v3");
    expect(html).toContain("Old client (MSA) · 15 Oct 2025");
  });

  it("puts the newest upload first and an unknown date last", () => {
    const at = (s: string) => html.indexOf(s);
    expect(at("New client")).toBeLessThan(at("Old client"));
    expect(at("Old client")).toBeLessThan(at("Undated client"));
  });

  it("names the client's paper and an undeclared source apart", () => {
    expect(html).toContain('label="Client documents"');
    expect(html).toContain('label="Source not declared"');
    expect(html).not.toContain("Previously uploaded");
  });
});
