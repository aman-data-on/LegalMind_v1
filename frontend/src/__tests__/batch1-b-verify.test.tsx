/**
 * Batch 1 slice B, verifier round 1: D1 (already with Legal at any stage), D3 (a point
 * waiting on the client), D4 (the queue counts points). Presentation only.
 */
import { describe, expect, it } from "vitest";

import { finalReady, pointCount } from "@/lib/labels";
import { canSendToLegalFor, nextStep } from "@/lib/nextStep";
import type { DealCounts, ReviewAssignments } from "@/lib/types";

const person = { user_id: "u2", name: "Counsel", email: "counsel@example.test" };
const assignOpen: ReviewAssignments = { assigned: [], can_send: true, eligible: [person] } as unknown as ReviewAssignments;
const answered: DealCounts = { changes_total: 4, changes_left: 0, changes_left_for_me: 0, changes_ours: 0,
                               points_open: 3, points_waiting: 0 };

/** The header's own chain: its inputs → canSendToLegalFor → nextStep, as RecordHeader runs it. */
function header(counts: DealCounts, assign: ReviewAssignments | null) {
  const stage = "CLIENT_RETURNED" as const;
  const canSendToLegal = canSendToLegalFor({ stage, counts, finalLatest: false, assign });
  return { canSendToLegal, step: nextStep({ stage, counts, viewer: "owner", canAnswer: true, canSendToLegal }) };
}

describe("D1: already with Legal, at any stage", () => {
  it("offers Send to Legal only while the points are not with Legal", () => {
    expect(header(answered, assignOpen)).toEqual({ canSendToLegal: true, step: { kind: "sendToLegal", label: "Send to Legal" } });
    // sent (or escalated): the server says so at CLIENT_RETURNED too — no send, no turn
    expect(header({ ...answered, sent_to_legal: true }, assignOpen)).toEqual({ canSendToLegal: false, step: null });
    // a reviewer just picked on this page, before the counts are read again
    const picked = { ...assignOpen, assigned: [{ ...person, assigned_by: "u1", assigned_at: "2026-11-09" }] };
    expect(header(answered, picked as ReviewAssignments).step).toBeNull();
  });
});

describe("D3: a point waiting on the client", () => {
  it("keeps the final contract back, and fails closed when unknown", () => {
    expect(finalReady({ ...answered, points_open: 0 })).toBe(true);
    expect(finalReady({ ...answered, points_open: 0, points_waiting: 1 })).toBe(false);
    const { points_waiting: _, ...unknown } = { ...answered, points_open: 0 };
    expect(finalReady(unknown)).toBe(false);
  });
});

describe("D4: the queue counts points", () => {
  it("counts findings that share a group once per review", () => {
    const row = (review: string, id: string, group_id?: string) =>
      ({ review: { id: review }, finding: group_id ? { id, group_id } : { id } });
    expect(pointCount([row("r1", "f1", "g"), row("r1", "f2", "g"), row("r1", "f3"), row("r2", "f4", "g")])).toBe(3);
  });
});
