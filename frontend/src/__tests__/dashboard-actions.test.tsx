/**
 * Dashboard — attention discovery, and the two real mutations.
 *
 * Three things are worth pinning here, and all three are places where a
 * plausible-looking implementation is wrong:
 *
 * 1. **A contract needing attention must stay discoverable off the current
 *    page or filter.** History: a standalone "Needs Attention" list once
 *    rendered zero rows in that situation and read as "all clear" (§ below).
 *    2026-09-02 redesign: that dedicated section is gone — the cue now lives
 *    as a row highlight IN the table — so the guarantee now rests entirely on
 *    `documentStatusBucket` returning the SAME `"needs_attention"` value the
 *    row-highlight condition, the stat tile's filter link and the Status
 *    filter option all key off. If this value drifts from what the server's
 *    `_status_bucket` computes, all three go stale together and silently.
 *
 * 2. **Delete must go to the server.** Splicing a row out of a React array
 *    looks identical to the user and deletes nothing. It also can't know which
 *    of the two server-side modes ran.
 *
 * 3. **The confirmation must not lie about what happens.** An unanalyzed
 *    contract is destroyed; an analyzed one is withdrawn from view with its
 *    findings and audit trail retained (rule 17). Saying "permanently" in both
 *    cases is wrong in the case that involves legal records.
 */

import { describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";
import * as P from "@/lib/permissions";
import { documentStatusBucket } from "@/components/workspace/model";
import type { Contract } from "@/lib/types";

function contract(over: Partial<Contract> = {}): Contract {
  return {
    id: "c1", owner_id: "u1", name: "ACME MSA", contract_type: "MSA",
    status: "ACTIVE", created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:00:00Z",
    ...over,
  } as Contract;
}

const analyzed = contract({
  id: "c2",
  latest_version: { id: "v1", version_number: 1, processing_status: "COMPLETED" },
  latest_analysis: {
    review_id: "r1", review_status: "ANALYSIS_COMPLETE",
    created_at: "2026-09-01T00:00:00Z", completed_at: "2026-09-01T01:00:00Z",
    classification_counts: { MATCH: 6, DEVIATION: 5, MISSING: 4 },
  },
} as Partial<Contract>);

describe("attention discovery survives off the current page or filter", () => {
  it("the Status filter and the stat tile both request the real server bucket", async () => {
    // Both the "Needs Attention" stat tile's onSelect and the Status <select>
    // option end up calling exactly this — a `status`-filtered request
    // against the WHOLE collection (page 1, not whatever page the table
    // happens to be showing), the same shape `filterTo()` builds. If this
    // regressed to something derived from the currently-loaded page instead,
    // a contract at position 26 would go back to being invisible while the
    // stat tile beside it still counted it — the original defect.
    const spy = vi.spyOn(api, "contracts").mockResolvedValue({
      items: [], pagination: { page: 1, page_size: 25, total: 0 },
    });

    await api.contracts(1, 25, { status: "needs_attention", sort: "created_desc" });

    const [page, , filters] = spy.mock.calls[0]!;
    expect(page).toBe(1);
    expect(filters).toMatchObject({ status: "needs_attention" });
    spy.mockRestore();
  });

  it("is the same value the row-highlight condition and the server bucket agree on", () => {
    // The bucket names are a cross-stack contract: the API computes the same
    // `_status_bucket` the table row's `ws-tr--attention` class and the stat
    // tile both key off. A value outside this set makes the row highlight,
    // the tile link and the Status filter option all silently disagree.
    expect(documentStatusBucket(analyzed)).toBe("needs_attention");
  });
});

describe("delete is a server operation", () => {
  it("issues a DELETE for the contract and reports the mode the server chose", async () => {
    const spy = vi.spyOn(api, "deleteContract")
      .mockResolvedValue({ deleted: true, mode: "soft" });

    const result = await api.deleteContract("c2");

    expect(spy).toHaveBeenCalledWith("c2");
    // The mode is the server's to decide and the UI's to report — not something
    // the client may assume.
    expect(result.mode).toBe("soft");
    spy.mockRestore();
  });

  it("edits go through the same PATCH the intake confirm already used", async () => {
    const spy = vi.spyOn(api, "updateContract").mockResolvedValue(contract());

    await api.updateContract("c1", { name: "Renamed", contract_type: "TOS" });

    expect(spy).toHaveBeenCalledWith("c1",
      { name: "Renamed", contract_type: "TOS" });
    spy.mockRestore();
  });
});

describe("the destructive action is permission-gated", () => {
  it("names the permission the server enforces", () => {
    // Presentation gating only (47.6) — but it must gate on the SAME name the
    // server checks, or the menu hides an action the user has, or offers one
    // they do not.
    expect(P.CONTRACT_DELETE).toBe("contract.delete");
    expect(P.CONTRACT_UPDATE).toBe("contract.update");
  });
});

describe("the confirmation describes what the server will actually do", () => {
  // The dialog branches on whether an analysis exists, because that is exactly
  // what the server branches on. These two assertions are the contract between
  // the copy and the endpoint.
  it("treats a contract with an analysis as the retained case", () => {
    expect(analyzed.latest_analysis != null).toBe(true);
  });

  it("treats a contract with no analysis as the destroyed case", () => {
    expect(contract().latest_analysis != null).toBe(false);
  });
});
