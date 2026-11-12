/**
 * The best-effort analysis chain — resolve the latest PUBLISHED configuration
 * snapshot, create the Review, run the analysis (2026-08-31 UX correction).
 *
 * One implementation for both entrances to the loop: the first upload and a
 * revised version. Best-effort by design: any failure here is a STATE the
 * workspace's findings pane explains honestly (no published snapshot, no
 * `review.create`) — never a dead
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
    const detail = await api.contract(contractId);
    // AM-51 (owner, 2026-09-09): the type is one optional signal — the engine
    // measures the document by its content, so the chain never waits for one.
    const versionId = detail.document_versions?.[0]?.id;
    if (!versionId) return;
    // A document still being processed (the deferred-OCR path) has no evidence
    // yet, and the server refuses to analyse it. Skip the whole chain — the
    // workspace watches processing and runs this chain when extraction
    // completes, so the analysis still happens without anyone waiting on it.
    // Only the in-between states skip: a FAILED extraction still gets its
    // Review and the honest ANALYSIS_FAILED surface, exactly as before.
    const version = await api.documentVersion(versionId);
    if (version.processing_status === "PENDING" ||
        version.processing_status === "PROCESSING") return;
    // AM-245: a paper the server reads as not a contract gets no Review here — the
    // findings pane says so and offers "Review anyway", which creates the one Review
    if (version.paper_kind?.kind === "NOT_A_CONTRACT" && !version.paper_kind.reviewed_anyway) {
      return;
    }
    // AM-321 r3: a scan's Review is opened by the server with its OCR result — never
    // a second one from this tab (a collaborator's chain included)
    const opened = await api.reviews({ contract_id: contractId, page_size: 100 });
    if (opened.items.some((r) => r.document_version_id === versionId)) return;
    await analyseVersion(versionId);
  } catch {
    // The workspace's findings pane states the real situation.
  }
}

/** "Analyse now" (`AM-317` r6, audit N6): this version's Review against the latest
 *  published standards, created and run. Throws, so the control can say why it could
 *  not; the server checks ownership and every other rule again. */
export async function analyseVersion(versionId: string): Promise<void> {
  const snapshot = (await api.snapshots({ page_size: 1 })).items[0];
  if (!snapshot) throw new Error("No standards are published yet, so there is nothing to analyse against.");
  const review = await api.createReview(versionId, snapshot.id);
  await api.analyzeReview(review.id);
}
