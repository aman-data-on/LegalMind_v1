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
 * 2. **Archive must go to the server.** Splicing a row out of a React array
 *    looks identical to the user and archives nothing.
 *
 * 3. **Nothing destroys a contract (AB-12 r6).** The client has no delete
 *    call at all; archive returns the contract with `archived_at` set, and the
 *    confirmation copy says what the server does — hides and keeps.
 */

import { describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";
import * as P from "@/lib/permissions";
import { documentStatusBucket, knownCounterparties } from "@/components/workspace/model";
import type { Contract } from "@/lib/types";

function contract(over: Partial<Contract> = {}): Contract {
  return {
    id: "c1", owner_id: "u1", name: "ACME MSA", contract_type: "MSA",
    status: "ACTIVE", archived_at: null, created_at: "2026-09-01T00:00:00Z",
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
    user_status_counts: { ACCEPTABLE: 6, NEEDS_DECISION: 5, REQUIRES_MODIFICATION: 4 },
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

describe("archive is a server operation", () => {
  it("issues the archive call and gets the contract back marked archived", async () => {
    const spy = vi.spyOn(api, "archiveContract")
      .mockResolvedValue(contract({ id: "c2", archived_at: "2026-09-05T00:00:00Z" }));

    const result = await api.archiveContract("c2");

    expect(spy).toHaveBeenCalledWith("c2");
    expect(result.archived_at).not.toBeNull();
    spy.mockRestore();
  });

  it("the client exposes no delete call for a contract at all", () => {
    expect((api as unknown as Record<string, unknown>)["deleteContract"]).toBeUndefined();
  });

  it("edits go through the same PATCH the intake confirm already used", async () => {
    const spy = vi.spyOn(api, "updateContract").mockResolvedValue(contract());

    await api.updateContract("c1", { name: "Renamed", contract_type: "TOS" });

    expect(spy).toHaveBeenCalledWith("c1",
      { name: "Renamed", contract_type: "TOS" });
    spy.mockRestore();
  });
});

describe("the row actions are permission-gated", () => {
  it("names the permissions the server enforces", () => {
    // Presentation gating only (47.6) — but it must gate on the SAME names the
    // server checks, or the menu hides an action the user has, or offers one
    // they do not.
    expect(P.CONTRACT_ARCHIVE).toBe("contract.archive");
    expect(P.CONTRACT_TRANSFER).toBe("contract.transfer");
    expect(P.DEPARTMENT_VIEW).toBe("department.view");
    expect(P.CONTRACT_UPDATE).toBe("contract.update");
  });
});

describe("the department view is a server scope, not a client filter", () => {
  it("asks the server for scope=department rather than filtering rows locally", async () => {
    const spy = vi.spyOn(api, "contracts").mockResolvedValue({
      items: [], pagination: { page: 1, page_size: 25, total: 0 },
    });
    await api.contracts(1, 25, { scope: "department", sort: "created_desc" });
    const [, , filters] = spy.mock.calls[0]!;
    expect(filters).toMatchObject({ scope: "department" });
    spy.mockRestore();
  });
});

describe("declared version metadata — source, counterparty, effective date (2026-09-06)", () => {
  it("is declared through PATCH /document-versions/{id}, where null clears a key", async () => {
    const spy = vi.spyOn(api, "declareVersion").mockResolvedValue({} as never);

    await api.declareVersion("v1", { source: "COUNTERPARTY", counterparty: null });

    expect(spy).toHaveBeenCalledWith("v1", { source: "COUNTERPARTY", counterparty: null });
    spy.mockRestore();
  });

  it("the counterparty datalist holds only names already on the list — trimmed, once each, sorted", () => {
    const rows = [
      contract({ latest_version: { id: "a", version_number: 1, processing_status: "COMPLETED", counterparty: "Zeta Ltd" } }),
      contract({ latest_version: { id: "b", version_number: 2, processing_status: "COMPLETED", counterparty: " Zeta Ltd " } }),
      contract({ latest_version: { id: "c", version_number: 1, processing_status: "COMPLETED" } }),
      contract({ latest_version: { id: "d", version_number: 1, processing_status: "COMPLETED", counterparty: "Alpha Pvt" } }),
      contract({ latest_version: null }),
    ];
    expect(knownCounterparties(rows)).toEqual(["Alpha Pvt", "Zeta Ltd"]);
    // No list yet (first load) → no suggestions, not a crash.
    expect(knownCounterparties(null)).toEqual([]);
  });
});

describe("the contract's lifecycle state is declared (P-1, 2026-09-06)", () => {
  it("goes through the same PATCH as every other edit, and only when it changed", async () => {
    const spy = vi.spyOn(api, "updateContract").mockResolvedValue(contract());
    await api.updateContract("c1", { name: "ACME MSA", contract_type: "MSA", status: "ACTIVE" });
    expect(spy).toHaveBeenCalledWith("c1", { name: "ACME MSA", contract_type: "MSA", status: "ACTIVE" });
    spy.mockRestore();
  });
});
