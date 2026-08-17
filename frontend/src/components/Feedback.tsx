"use client";

/**
 * Shared status and error presentation — locked 49.5, 49.9, 52.4.
 *
 * The request id is shown with every failure. Locked 49.9 makes it the correlation
 * anchor between a request and the audit events it produced, so quoting it is what
 * lets an operator find what happened without the user having to reconstruct it.
 */

import { ApiError } from "@/lib/api";

export function ErrorBanner({ error }: { error: unknown }) {
  if (!error) return null;

  if (error instanceof ApiError) {
    return (
      <div className="banner banner--error" role="alert">
        <p>{message(error)}</p>
        <p className="hint">
          {error.code} · reference {error.requestId}
        </p>
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

  return (
    <div className="banner banner--error" role="alert">
      <p>The request could not be completed.</p>
    </div>
  );
}

function message(error: ApiError): string {
  if (error.isUnauthenticated) return "Your session has ended. Please sign in again.";
  /*
   * 49.5 r1 / 52.4 — an out-of-scope object and a nonexistent one are
   * byte-identical on the wire and must read identically here. Wording such as
   * "you do not have access to this Review" would hand back the existence
   * disclosure the identical response exists to prevent.
   */
  if (error.isNotFound) return "Not found.";
  if (error.isRateLimited) return "Too many requests. Please try again shortly.";
  return error.message;
}

export function Loading({ what }: { what: string }) {
  return <p className="hint">Loading {what}…</p>;
}

export function EmptyState({ children }: { children: React.ReactNode }) {
  return <p className="empty">{children}</p>;
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
