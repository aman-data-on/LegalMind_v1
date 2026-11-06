"use client";

/**
 * "Re-analyse with the latest standards" (owner, 2026-10-26). Publishing new
 * standards never changes an existing Review (rule 16), so a contract analysed
 * before a fix keeps its old result until someone asks again. This asks again:
 * a NEW Review of the version on screen against the latest published snapshot,
 * created and run as the person who clicks (their audit trail, never anyone
 * else's). The earlier Review and its decisions stay, as history.
 *
 * Shown only when it would change something: the Review on screen was analysed
 * against an older snapshot than the latest published one. The server decides
 * whether this person may create the Review (47.6: the contract's owner).
 */

import { useEffect, useState } from "react";
import { api, describeError } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import { useFindingsStateOptional } from "./findingsState";

export function ReanalyseNotice({ documentVersionId, snapshotId, onStarted }: {
  documentVersionId: string;
  snapshotId: string;
  onStarted: () => void;
}) {
  const { can } = useSession();
  const owner = useFindingsStateOptional()?.isOwner ?? true;
  const [latest, setLatest] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refused, setRefused] = useState(false);

  useEffect(() => {
    let live = true;
    api.snapshots({ page_size: 1 })
      .then(({ items }) => { if (live) setLatest(items[0]?.id ?? null); })
      .catch(() => { /* no notice: nothing to compare with */ });
    return () => { live = false; };
  }, [snapshotId]);

  if (!can(P.REVIEW_CREATE) || !owner || !latest || latest === snapshotId) return null;

  async function reanalyse() {
    setBusy(true);
    setError(null);
    try {
      // AM-245: never create a Review the gate will refuse — a new empty one would hide
      // the result this notice promises stays as it is
      const version = await api.documentVersion(documentVersionId);
      if (version.paper_kind?.kind === "NOT_A_CONTRACT" && !version.paper_kind.reviewed_anyway) {
        setRefused(true);
        setBusy(false);
        return;
      }
      const review = await api.createReview(documentVersionId, latest!);
      const done = await api.analyzeReview(review.id);
      if (done.not_a_contract) {    // AM-245: nothing ran; the old result stands
        setRefused(true);
        setBusy(false);
        return;
      }
      onStarted();
    } catch (e) {
      setError(describeError(e));
      setBusy(false);
    }
  }

  return (
    <div className="ws-pane__note" role="status">
      <p>Our standards have changed since this analysis. This result stays until you analyse again.</p>
      <button type="button" className="ws-btn ws-btn--sm" onClick={reanalyse} disabled={busy}>
        {busy ? "Starting the new analysis…" : "Re-analyse with the latest standards"}
      </button>
      {refused ? <p>This doesn&rsquo;t look like a contract or one of our policies, so it
        was not analysed again.</p> : null}
      {error ? <p role="alert">{error}</p> : null}
    </div>
  );
}
