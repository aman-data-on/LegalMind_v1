/** Lawyer judgement P1 (`AM-476`): what the client's paper replaces in our paper — the
 *  server's rows as sent; the UI presents them and decides nothing (rule 18). */
import { api } from "./api";

export type PaperPin = { label?: string; file?: string; sha256?: string; date?: string; how?: string; unresolved?: string;
  picked?: { by: string | null; by_you: boolean; on: string };
  hint?: { on?: string; earliest?: string | null; choices?: Array<{ label: string; template_version_id?: string; contract_id?: string; file?: string; sha256?: string }>;
           fingerprint?: Array<{ label: string; fits: number; of: number }> } };
export type PaperRow = {
  source: string | null; doc: "MSA" | "TOS" | "SLA" | "AUP"; mode: "NUMBERED" | "DESCRIBED"; number: string | null; sub: string | null;
  title: string | null; described: string | null; verb: string; client_quote: string; status: string;
  hint?: PaperPin["hint"]; ours?: { title: string | null; quote: string }; markers?: string[]; blank?: string;
  changed_since?: PaperPin;
};
export type OurPaper = { version_number: number; on: string; on_from: "DOCUMENT" | "UPLOAD"; rows: PaperRow[];
  pins?: Record<string, PaperPin>; overrides?: string[]; overrides_count?: number; overrides_by_doc?: Record<string, number>;
  can_pick?: boolean; more_for_legal?: number };

/** One fetch per contract, shared by the Changes panel, each change card and the brief
 *  (round 2): a reload (after Legal's pick) refetches once and tells every reader. */
const cache = new Map<string, Promise<OurPaper>>();
const listeners = new Map<string, Set<() => void>>();

export function ourPaper(contractId: string): Promise<OurPaper> {
  let p = cache.get(contractId);
  if (!p) {
    p = api.ourPaper(contractId);
    p.catch(() => cache.delete(contractId));   // a failed read is retried, never cached
    cache.set(contractId, p);
  }
  return p;
}

export function reloadOurPaper(contractId: string): void {
  cache.delete(contractId);
  listeners.get(contractId)?.forEach((f) => f());
}

export function onOurPaper(contractId: string, f: () => void): () => void {
  const set = listeners.get(contractId) ?? new Set();
  set.add(f);
  listeners.set(contractId, set);
  return () => { set.delete(f); };
}
