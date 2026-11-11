/**
 * What we can offer — the negotiation playbook (`AM-305`). The server derives every
 * line from our paper and the ratified standard (`analysis.playbook`); this file only
 * types it and says, for a client change, which line it touches. Whether the change is
 * inside the line is the server's `effect_for_us`, never re-derived here (rule 18).
 */

import type { ClientChange } from "./changes";

export type OfferKind = "RANGE" | "EXACT" | "LEGAL_ONLY";

export interface PlaybookPoint {
  requirement_code: string;
  kind: OfferKind;
  /** our paper's own figure, as the engine read it; null when it read none */
  opening: { value: number; unit: string; basis: string | null } | null;
  /** the line in plain words, e.g. "We start at 7 days. You can agree up to 21 days. …" */
  line: string;
  /** something lies between our opening and our limit — the deal owner's to agree */
  room: boolean;
}

export interface Playbook { points: PlaybookPoint[] }

/** The points with room to agree first; the fixed figures, then the points Legal alone
 *  decides, folded after them. */
export function grouped(points: PlaybookPoint[]) {
  return {
    room: points.filter((p) => p.room),
    fixed: points.filter((p) => !p.room && p.kind !== "LEGAL_ONLY"),
    legal: points.filter((p) => p.kind === "LEGAL_ONLY"),
  };
}

/** The playbook line a client change touches, and whether the server already reads it
 *  as within (Better or No change for us). Null: no line with a figure covers it. */
export function offerFor(change: ClientChange, points: PlaybookPoint[] | null):
    { point: PlaybookPoint; within: boolean; fallback: boolean } | null {
  // a NEGATIVE row not measured worse (unmeasured, absent) is never "beyond" our offer
  if (!points || (change.effect_for_us === "NEGATIVE" && change.measured !== "WORSE")) return null;
  const codes = new Set([...change.review.after, ...(change.after ? [] : change.review.before)]
    .map((f) => f.requirement_code));
  const point = points.find((p) => p.kind !== "LEGAL_ONLY" && codes.has(p.requirement_code));
  return point ? { point, within: change.effect_for_us !== "NEGATIVE",
                   fallback: change.effect_for_us === "FALLBACK" } : null;
}

export const OFFER_WORDS = {
  within: "Within what we can offer — you can accept",
  fallback: "Fallback — you can accept",
  beyond: "Beyond what we can offer — Legal decides",
} as const;
