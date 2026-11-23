/**
 * The deal brief (batch 3+4, AB-218): the wire shape of
 * `GET /contracts/{id}/brief` and the few pure helpers that word it. Every number is
 * the server's (`deal_counts`, the one count); nothing here decides who acts — the
 * sentences only read the counts and the deal's stage (rule 18).
 */

import { BRIEF_STATUS } from "@/lib/labels";
import type { DealCounts, PriorPaper } from "@/lib/types";

export type Tie = "AS_TOLD" | "BEYOND";

/** What we told the client. A writer (Legal) also gets the key, version and ties. */
export interface Told {
  text: string;
  told_on: string | null;
  position_key?: string;
  version_number?: number;
  ties?: Record<string, Tie>;
  recorded_by?: string | null;
  recorded_at?: string;
}

export interface BriefAsk { title: string; clause: string | null; quote: string; removed: boolean; row_key: string }

export interface DealBrief {
  counts: DealCounts;
  /** absent with no round of changes for a deal owner (the points line stands in) */
  status?: BriefStatus;
  /** one line per clause group the client changed (absent with no round) */
  asks?: BriefAsk[];
  asks_more?: number;
  /** batch 8 R2.5: changes with no tracked change and no highlight — absent when none */
  not_marked?: { count: number; total: number; highlights_read: boolean; more: number;
                 /** `title` is the clause's heading, absent when it has none */
                 rows: (Omit<BriefAsk, "title"> & { title?: string })[] };
  /** batch 8 R1.4: changes already in an earlier signed or final contract (absent: none) */
  already_agreed?: { count: number; rows: string[]; contract: PriorPaper };
  /** batch 8 R5.3: the standard sets that measured the paper (absent: none known); each
   *  source's name and points only for Legal (omitted otherwise) */
  measured_against?: { kind: string; name?: string; points?: number }[];
  /** batch 8 R5.4 (C-34 open): our MSA's terms measured paper that is not an MSA */
  measured_against_note?: "MSA_TERMS_ON_OTHER_PAPER";
  /** omitted for a reader without positions (LEGAL-02) */
  told?: Told[];
  our_mistake?: string;
  /** `legal.decision` holders only */
  legal?: {
    beyond: { row_key: string; clause: string }[];
    as_told: number;
    not_discussed: number;
    comments: string[];
    whole_contract: { finding_id: string; title: string }[];
    note?: string;
    can_record: boolean;
  };
}

/** The body a position is written with (`POST …/positions[/{key}]`). */
export interface TellBody { text: string; told_on?: string | null; ties?: Record<string, Tie>; withdrawn?: boolean; expected_version?: number }

/** Who acts next — the server's code (`GET …/brief`, rule 18); the screen only words it. */
export type BriefStatus = "NOT_SENT" | "WITH_LEGAL" | "WITH_LEGAL_AND_YOURS" | "YOURS_TO_ANSWER" | "POINTS_OPEN"
  | "SEND_POINTS_TO_LEGAL" | "SEND_REPLY" | "ALL_ANSWERED" | "REPLY_READY" | "WITH_CLIENT" | "LEGAL_QUEUE"
  | "LEGAL_POINTS" | "LEGAL_NOTHING" | "CHECKING" | "FINAL_READY" | "PREPARE_FINAL" | "ON_HOLD";

/** The status line in words: the server's code, its numbers from the one count. */
export function statusWords(brief: Pick<DealBrief, "status" | "counts">): string | null {
  const c = brief.counts;
  return brief.status ? BRIEF_STATUS[brief.status](c.changes_left_legal ?? 0, c.changes_left_for_me ?? 0, c.points_open ?? 0) : null;
}

/** Open a change on the Changes tab — the brief's links (the pane listens). */
const OPEN = "lm:open-change";
export function openChange(rowKey: string): void {
  window.dispatchEvent(new CustomEvent<string>(OPEN, { detail: rowKey }));
}
export function onOpenChange(handler: (rowKey: string) => void): () => void {
  const listen = (event: Event) => handler((event as CustomEvent<string>).detail);
  window.addEventListener(OPEN, listen);
  return () => window.removeEventListener(OPEN, listen);
}
