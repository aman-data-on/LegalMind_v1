"use client";

/**
 * The shared states — error, loading, empty (UX Batch 2; GP-3, GP-4, GP-24) — and the
 * legacy `ErrorBanner` they replaced the wording of. Locked 49.5, 49.9, 52.4 still hold:
 *
 * - An error says what failed (title, no full stop), why (the server's sentence, through
 *   `describeError`) and the fix, with one "Try again". It never renders beside a loading
 *   indicator: callers show loading only while `data === null && !error`.
 * - The request id (49.9, the correlation anchor) is printed only when there IS one —
 *   "Reference -" was the old line for a response without one.
 * - Not-found stays the one identical sentence for every cause (49.5 r1 / 52.4).
 */

import { ApiError, describeError } from "@/lib/api";
import { FEEDBACK_COPY } from "@/lib/labels";
import { IconAlertCircle } from "@/components/workspace/icons";

/** The id support can look up, or null when the response carried none. */
export function supportReference(error: unknown): string | null {
  if (!(error instanceof ApiError)) return null;
  const id = error.requestId?.trim();
  return id && id !== "-" ? id : null;
}

/** The fix for a failure the reader can only retry (network, 5xx, rate limit). A refusal
 *  the server explained (401, 404, a validation) carries its own next step already. */
function transient(error: unknown): boolean {
  return !(error instanceof ApiError) || error.status === 0 || error.status >= 500 || error.isRateLimited;
}

export function ErrorState({ title, fix, error, onRetry, heading: Heading = "h2", children }: {
  /** what failed, without a full stop: "Standards could not be loaded" */
  title: string;
  /** what to do; defaults to the connection fix for a transient failure */
  fix?: string | null;
  error?: unknown;
  onRetry?: () => void;
  /** "h1" where the error IS the page (an error boundary in the shell) */
  heading?: "h1" | "h2" | "h3";
  /** an extra control a caller needs (a declare-roles form, a link home) */
  children?: React.ReactNode;
}) {
  const why = error ? describeError(error) : null;
  const next = fix === undefined ? (error === undefined || transient(error) ? FEEDBACK_COPY.defaultFix : null) : fix;
  const reference = supportReference(error);
  return (
    <div className="lm-state lm-state--error" role="alert">
      <span className="lm-state__icon"><IconAlertCircle size={20} /></span>
      <div className="lm-state__text">
        <Heading className="lm-state__title">{title}</Heading>
        {why ? <p className="lm-state__body">{why}</p> : null}
        {next ? <p className="lm-state__body">{next}</p> : null}
        {children}
        {onRetry ? (
          <p className="lm-state__acts">
            <button type="button" className="ws-btn" onClick={onRetry}>{FEEDBACK_COPY.retry}</button>
          </p>
        ) : null}
        {reference ? <p className="lm-state__ref">{FEEDBACK_COPY.reference(reference)}</p> : null}
      </div>
    </div>
  );
}

/** Fixed-height skeleton rows (shape only, no shimmer) and the word, announced once. */
export function LoadingState({ label = FEEDBACK_COPY.loading, rows = 0 }: { label?: string; rows?: number }) {
  return (
    <div className="lm-state lm-state--loading" role="status" aria-live="polite">
      <p className="lm-state__body">{label}</p>
      {rows > 0 ? (
        <div className="lm-skel" aria-hidden="true">
          {Array.from({ length: rows }, (_, i) => <span key={i} className="lm-skel__row" />)}
        </div>
      ) : null}
    </div>
  );
}

/** One centred block in the pane that would hold the content: what is true, what to do,
 *  and the one action. */
export function EmptyState({ icon, title, body, action, children }: {
  icon?: React.ReactNode;
  title?: string;
  body?: React.ReactNode;
  action?: React.ReactNode;
  /** the older one-sentence form (`<EmptyState>No rows.</EmptyState>`) */
  children?: React.ReactNode;
}) {
  return (
    <div className="lm-state lm-state--empty">
      {icon ? <span className="lm-state__icon" aria-hidden="true">{icon}</span> : null}
      {title ? <p className="lm-state__title">{title}</p> : null}
      {(body ?? children) ? <p className="lm-state__body">{body ?? children}</p> : null}
      {action ? <p className="lm-state__acts">{action}</p> : null}
    </div>
  );
}

/** The legacy screens' banner (sign-in, Standards, Departments): the same reference rule. */
export function ErrorBanner({ error }: { error: unknown }) {
  if (!error) return null;

  if (error instanceof ApiError) {
    const reference = supportReference(error);
    return (
      <div className="banner banner--error" role="alert">
        <p>{message(error)}</p>
        {/* the request id lets support find what happened (49.9); the raw code is theirs
            to read in the log, not the reader's (B13) */}
        {reference ? <p className="hint">{FEEDBACK_COPY.reference(reference)}</p> : null}
        {error.fields && error.fields.length > 0 ? (
          <ul className="banner__fields">
            {error.fields.map((field) => (
              /*
                49.5 r4 — the API lists offending fields without echoing the
                submitted values, so there is nothing here to leak back.
              */
              <li key={`${field.field}:${field.code}`}>
                {field.field || "request"}: {field.code}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    );
  }

  // QA-064: a field the reader can fix, said by name — never the generic line
  const fixable = error instanceof Error && error.name === "InputError";
  return (
    <div className="banner banner--error" role="alert">
      <p>{fixable ? (error as Error).message : "The request could not be completed."}</p>
    </div>
  );
}

function message(error: ApiError): string {
  if (error.isUnauthenticated) return "Your session has ended. Sign in again.";
  /*
   * 49.5 r1 / 52.4 — an out-of-scope object and a nonexistent one are
   * byte-identical on the wire and must read identically here. Wording such as
   * "you do not have access to this Review" would hand back the existence
   * disclosure the identical response exists to prevent.
   */
  if (error.isNotFound) return "Not found.";
  if (error.isRateLimited) return "Too many requests. Try again shortly.";
  return error.message;
}

/** The legacy one-line loading row, now the shared state. */
export function Loading({ what }: { what: string }) {
  return <LoadingState label={`Loading ${what}…`} />;
}

export function Pager({
  page,
  pageSize,
  total,
  onPage,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPage: (page: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (total === 0) return null;
  return (
    <nav className="pager">
      <button type="button" disabled={page <= 1} onClick={() => onPage(page - 1)}>
        Previous
      </button>
      <span>
        Page {page} of {pages} · {total} total
      </span>
      <button type="button" disabled={page >= pages} onClick={() => onPage(page + 1)}>
        Next
      </button>
    </nav>
  );
}
