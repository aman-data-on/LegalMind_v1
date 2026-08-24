"use client";

/**
 * One contract: its document versions, upload, and starting a Review — locked 52.6
 * (Steps 2, 34, 9), 49.3, 34.5, 34.15.
 *
 * Two locked behaviours are visible here.
 *
 * **A duplicate upload is reported, never silently suppressed** (34.5): whether a
 * re-upload is a new contractual version is a business decision (Step 33.9), so the
 * UI states that the file matched an existing version and leaves the judgement to
 * the user.
 *
 * **Extraction status is separate from Review status** (34.15, Step 30 r13). They
 * are shown as two different columns and never merged into one "progress" value —
 * `ANALYSIS_FAILED` is not `UNABLE_TO_EVALUATE` and a failed parse is not a legal
 * conclusion (34.9).
 */

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import { AccessRestricted, PermissionGate } from "@/components/AccessRestricted";
import { EmptyState, ErrorBanner, Loading } from "@/components/Feedback";
import { Field, StatePill, TableCard, formatDate } from "@/components/Primitives";
import { api } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { Contract, Review, UploadResult } from "@/lib/types";

export default function ContractPage({
  params,
}: {
  params: Promise<{ contractId: string }>;
}) {
  const { can } = useSession();
  const [contractId, setContractId] = useState<string | null>(null);
  const [contract, setContract] = useState<Contract | null>(null);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [uploads, setUploads] = useState<UploadResult[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const [snapshotId, setSnapshotId] = useState("");

  useEffect(() => {
    void params.then((resolved) => setContractId(resolved.contractId));
  }, [params]);

  const load = useCallback(async () => {
    if (!contractId) return;
    setError(null);
    try {
      setContract(await api.contract(contractId));
      const result = await api.reviews({ page_size: 100 });
      setReviews(result.items.filter((review) => review.contract_id === contractId));
    } catch (cause) {
      setError(cause);
    }
  }, [contractId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!can(P.CONTRACT_VIEW)) return <AccessRestricted what="contracts" />;
  if (!contractId) return <Loading what="contract" />;

  async function upload(event: React.FormEvent) {
    event.preventDefault();
    const file = fileInput.current?.files?.[0];
    // Re-checked inside the handler rather than relying on the guard above: this
    // is a hoisted declaration, so the narrowing from the early return does not
    // reach it.
    if (!file || !contractId) return;
    setBusy(true);
    setError(null);
    try {
      const result = await api.uploadDocument(contractId, file);
      setUploads((previous) => [result, ...previous]);
      if (fileInput.current) fileInput.current.value = "";
      await load();
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(false);
    }
  }

  async function startReview(documentVersionId: string) {
    setError(null);
    try {
      await api.createReview(documentVersionId, snapshotId);
      await load();
    } catch (cause) {
      setError(cause);
    }
  }

  return (
    <>
      <Link className="page-back" href="/contracts">
        ← Contracts
      </Link>
      <h1>{contract?.name ?? "Contract"}</h1>
      {contract ? (
        <p className="page-meta">
          <span>{contract.contract_type ?? "Type not set"}</span>
          <StatePill axis="status" value={contract.status} />
        </p>
      ) : null}
      <ErrorBanner error={error} />

      <PermissionGate granted={can(P.DOCUMENT_UPLOAD)}>
        <form className="card form-row" onSubmit={upload}>
          <Field id="document-file" label="Upload a document version (PDF or DOCX)" grow>
            <input id="document-file" ref={fileInput} type="file" accept=".pdf,.docx" required />
          </Field>
          <button type="submit" className="btn btn--primary" disabled={busy}>
            {busy ? "Uploading…" : "Upload"}
          </button>
        </form>
      </PermissionGate>

      {uploads.length > 0 ? (
        <section className="card">
          <h2>This session&rsquo;s uploads</h2>
          {uploads.map((result) => (
            <div key={result.document_version.id}>
              <p>
                <strong>{result.document_version.original_filename}</strong> — version{" "}
                {result.document_version.version_number},{" "}
                {result.evidence_count} evidence extract
                {result.evidence_count === 1 ? "" : "s"}
              </p>
              <p className="hint">
                Processing {result.document_version.processing_status} · extraction{" "}
                {result.document_version.extraction_status ?? "not recorded"}
              </p>
              {result.duplicate_of ? (
                <p className="warning">
                  This file is byte-identical to an existing version of this contract.
                  It was stored as a new version anyway — whether that is correct is a
                  business decision, not something the system decides.
                </p>
              ) : null}
              {result.diagnostics.length > 0 ? (
                <details>
                  <summary>Extraction diagnostics ({result.diagnostics.length})</summary>
                  <p className="hint">
                    Information about reading the file. Not a legal conclusion.
                  </p>
                  <ul>
                    {result.diagnostics.map((note, index) => (
                      <li key={index}>{note}</li>
                    ))}
                  </ul>
                </details>
              ) : null}
              <p>
                <PermissionGate granted={can(P.DOCUMENT_DOWNLOAD)}>
                  <a href={api.documentContentUrl(result.document_version.id)}>
                    Download original
                  </a>
                </PermissionGate>
              </p>
            </div>
          ))}
        </section>
      ) : null}

      <h2>Reviews of this contract</h2>
      {reviews.length === 0 ? (
        <EmptyState>No reviews yet.</EmptyState>
      ) : (
        <TableCard>
          <table>
            <thead>
              <tr>
                <th>Review</th>
                <th>Status</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {reviews.map((review) => (
                <tr key={review.id}>
                  <td>
                    <Link href={`/reviews/${review.id}`}>{review.id.slice(0, 8)}</Link>
                  </td>
                  <td>
                    <StatePill axis="status" value={review.status} />
                  </td>
                  <td>{formatDate(review.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableCard>
      )}

      <PermissionGate granted={can(P.REVIEW_CREATE)}>
        <section className="card">
          <h2>Start a review</h2>
          <p className="hint">
            A Review is pinned to one document version and one published
            configuration snapshot, which is what makes it reproducible. Publish
            configuration first if you have no snapshot.
          </p>
          <form
            className="form-row"
            onSubmit={(event) => {
              event.preventDefault();
              const versionId = new FormData(event.currentTarget).get("version");
              if (typeof versionId === "string" && versionId) void startReview(versionId);
            }}
          >
            <Field id="review-version" label="Document version id">
              <input id="review-version" name="version" required />
            </Field>
            <Field id="review-snapshot" label="Configuration snapshot id">
              <input
                id="review-snapshot"
                required
                value={snapshotId}
                onChange={(event) => setSnapshotId(event.target.value)}
              />
            </Field>
            <button type="submit" className="btn btn--primary">
              Create review
            </button>
          </form>
        </section>
      </PermissionGate>
    </>
  );
}
