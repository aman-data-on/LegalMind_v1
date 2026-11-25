"use client";

import { api } from "@/lib/api";
import type { DocumentVersion, VersionComparison as Comparison } from "@/lib/types";

const label = (version: DocumentVersion) => `Version ${version.version_number}`;

/** The comparison's header — "Version 1 → Version 2", the two selects styled as the words they
 *  replace. Its own small module (W2 r2): the placeholder shown while the comparison's script
 *  loads draws this same header, so nothing moves when the real pane replaces it. */
export function CompareHead({ versions, before, after, onBefore, onAfter, counts }: {
  versions: DocumentVersion[]; before: string; after: string;
  onBefore?: (id: string) => void; onAfter?: (id: string) => void; counts: string | null;
}) {
  return (
    <div className="ws-compare__head">
      <div className="ws-compare__pair">
        <label className="ws-compare__pick">
          <span className="ws-visually-hidden">Earlier version</span>
          <select value={before} disabled={!onBefore} onChange={(event) => onBefore?.(event.target.value)}>
            {versions.map((version) => (
              <option key={version.id} value={version.id}>
                {label(version)}
              </option>
            ))}
          </select>
        </label>
        <span className="ws-compare__arrow" aria-hidden="true">→</span>
        <label className="ws-compare__pick">
          <span className="ws-visually-hidden">Later version</span>
          <select value={after} disabled={!onAfter} onChange={(event) => onAfter?.(event.target.value)}>
            {versions.map((version) => (
              <option key={version.id} value={version.id}>
                {label(version)}
              </option>
            ))}
          </select>
        </label>
      </div>
      {counts ? <p className="ws-compare__counts">{counts}</p> : null}
    </div>
  );
}

/** While the comparison's script loads: the same header and the same "Comparing…" line. */
export function CompareLoading({ versions }: { versions: DocumentVersion[] }) {
  return (
    <section className="ws-compare" aria-label="Compare versions" aria-busy="true">
      <CompareHead versions={versions} before={versions[1]?.id ?? ""} after={versions[0]?.id ?? ""} counts={null} />
      <p className="ws-pane__note">Comparing…</p>
    </section>
  );
}

/** W2 r2: the default comparison (the two newest versions) is asked for when ⋯ opens, beside the
 *  pane's script, and kept for the one pane that mounts next — so the pane opens already filled
 *  and the page does not move after the tap. Taken once; a failure is simply asked again. */
type Prefetched = { promise: Promise<Comparison>; value?: Comparison };
const prefetched = new Map<string, Prefetched>();
const keyOf = (contractId: string, before: string, after: string) => `${contractId}:${before}:${after}`;

export function prefetchComparison(contractId: string, versions: DocumentVersion[]): void {
  const before = versions[1]?.id, after = versions[0]?.id;
  if (!before || !after) return;
  const key = keyOf(contractId, before, after);
  if (prefetched.has(key)) return;
  const entry: Prefetched = { promise: api.versionComparison(contractId, before, after) };
  entry.promise.then((value) => { entry.value = value; }, () => { prefetched.delete(key); });
  prefetched.set(key, entry);
}

export function takeComparison(contractId: string, before: string, after: string): Prefetched | undefined {
  const key = keyOf(contractId, before, after);
  const entry = prefetched.get(key);
  prefetched.delete(key);
  return entry;
}
