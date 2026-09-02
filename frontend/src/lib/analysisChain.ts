/**
 * The best-effort analysis chain — resolve the latest PUBLISHED configuration
 * snapshot, create the Review, run the analysis (2026-08-31 UX correction).
 *
 * One implementation for both entrances to the loop: the first upload and a
 * revised version. Best-effort by design: any failure here is a STATE the
 * workspace's findings pane explains honestly (no published snapshot, no
 * `review.create`, type undeclared → the engine's own refusal) — never a dead
 * end and never a thrown error that would abandon the upload the user already
 * completed.
 */

import { api } from "./api";

export async function chainAnalysis(
  contractId: string,
  canCreateReview: boolean,
): Promise<void> {
  if (!canCreateReview) return;
  try {
    const snapshots = await api.snapshots({ page_size: 1 });
    const snapshot = snapshots.items[0];
    if (!snapshot) return;
    const detail = await api.contract(contractId);
    const versionId = detail.document_versions?.[0]?.id;
    if (!versionId) return;
    const review = await api.createReview(versionId, snapshot.id);
    await api.analyzeReview(review.id);
  } catch {
    // The workspace's findings pane states the real situation.
  }
}
