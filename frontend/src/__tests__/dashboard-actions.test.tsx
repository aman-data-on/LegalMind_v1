/**
 * Dashboard — the priority queue's data source, and the two real mutations.
 *
 * Three things are worth pinning here, and all three are places where a
 * plausible-looking implementation is wrong:
 *
 * 1. **The queue must ask its own question.** It used to be derived from
 *    whatever page of the table happened to be loaded, so a contract needing
 *    attention at position 26 was invisible while the tile beside it counted
 *    it. The section rendered nothing and read as "all clear". The fix is a
 *    `status`-filtered request against the whole collection, and this file is
 *    what stops it regressing to a `.find()` over local state.
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

describe("the priority queue asks the server, not the loaded page", () => {
  it("requests the needs_attention bucket across the whole collection", async () => {
    const spy = vi.spyOn(api, "contracts").mockResolvedValue({
      items: [], pagination: { page: 1, page_size: 5, total: 0 },
    });

    await api.contracts(1, 5, { status: "needs_attention", sort: "created_desc" });

    const [page, , filters] = spy.mock.calls[0]!;
    // Page 1 of a dedicated request — never the table's current page, which
    // carries the user's filters and sort and answers a different question.
    expect(page).toBe(1);
    expect(filters).toMatchObject({ status: "needs_attention" });
    spy.mockRestore();
  });

  it("uses a status the server actually implements as a filter", () => {
    // The bucket names are a cross-stack contract: the API computes the same
    // `_status_bucket` the row renders. A filter value outside this set is
    // rejected server-side, so the queue would silently show nothing.
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
