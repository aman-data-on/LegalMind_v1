"use client";

/**
 * Ask history — P1 (PRODUCT_UX_ROADMAP §E screen 9). The caller's OWN
 * conversations, scoped by the server to `user_id` (`AM-25` r7: the list can
 * never enumerate anyone else's questions). Asking happens in each document's
 * workspace; this screen is for rereading.
 *
 * The list and one recorded conversation both live at the fixed pathname
 * `/dashboard/ask`; which one renders is decided by `?id=` rather than a path
 * segment, so no conversation id appears in the URL path itself.
 */

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";

import { api, describeError } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { ConversationSummary, Pagination } from "@/lib/types";

import { ConversationView } from "@/components/workspace/ConversationView";

const PAGE_SIZE = 25;

function AskHistoryListView() {
  const { can } = useSession();
  const [conversations, setConversations] = useState<ConversationSummary[] | null>(null);
  const [names, setNames] = useState<Record<string, string>>({});
  const [pagination, setPagination] = useState<Pagination | null>(null);
  const [page, setPage] = useState(1);
  const [error, setError] = useState<unknown>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const result = await api.conversations({ page, page_size: PAGE_SIZE });
      setConversations(result.items);
      setPagination(result.pagination);
      const ids = [...new Set(result.items.map((c) => c.contract_id).filter((id): id is string => id !== null))];
      const settled = await Promise.allSettled(ids.map((id) => api.contract(id)));
      const found: Record<string, string> = {};
      ids.forEach((id, index) => {
        const outcome = settled[index];
        if (outcome?.status === "fulfilled") found[id] = outcome.value.name;
      });
      setNames(found);
    } catch (cause) {
      setError(cause);
    }
  }, [page]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!can(P.ASSIST_ASK)) {
    return (
      <div className="ws-state" role="note">
        <h2>Access restricted</h2>
        <p>Your account does not include Ask access.</p>
      </div>
    );
  }

  return (
    <>
      <div className="ws-context">
        <h1>Ask history</h1>
        {pagination ? (
          <span className="ws-context__meta ws-mono">{pagination.total} total</span>
        ) : null}
      </div>
      <div className="ws-docs">
        {error ? (
          <div className="ws-state ws-state--error" role="alert">
            <h2>Ask history could not be loaded.</h2>
            <p>{describeError(error)}</p>
          </div>
        ) : null}

        {conversations === null && !error ? (
          <div className="ws-docs__table" aria-busy="true">
            <p className="ws-visually-hidden" role="status" aria-live="polite">
              Loading ask history…
            </p>
            {[0, 1, 2].map((row) => (
              <div key={row} className="ws-docs__skel" aria-hidden="true">
                <span className="ws-skel ws-skel--line" style={{ width: "55%" }} />
                <span className="ws-skel ws-skel--line" style={{ width: "12%" }} />
                <span className="ws-skel ws-skel--line" style={{ width: "10%" }} />
              </div>
            ))}
          </div>
        ) : null}

        {conversations !== null && conversations.length === 0 ? (
          <div className="ws-state">
            <h2>No questions yet.</h2>
            <p>
              Ask lives in each document&rsquo;s workspace — open a document and ask about it
              there. Every conversation is saved here for rereading.
            </p>
          </div>
        ) : null}

        {conversations !== null && conversations.length > 0 ? (
          <div className="ws-docs__table">
            <table>
              <thead>
                <tr>
                  <th scope="col">First question</th>
                  <th scope="col">Turns</th>
                  <th scope="col">Document</th>
                  <th scope="col">Started</th>
                </tr>
              </thead>
              <tbody>
                {conversations.map((conversation) => (
                  <tr key={conversation.id}>
                    <td className="ws-docs__q">
                      <Link href={`/dashboard/ask?id=${conversation.id}`}>
                        {conversation.first_question ?? "(nothing asked)"}
                      </Link>
                    </td>
                    <td className="ws-mono">{conversation.message_count}</td>
                    <td>
                      {conversation.contract_id ? (
                        <Link href={`/dashboard?id=${conversation.contract_id}`}>
                          {names[conversation.contract_id] ?? conversation.contract_id.slice(0, 8)}
                        </Link>
                      ) : (
                        "—"
                      )}
                    </td>
                    <td className="ws-mono">
                      {conversation.created_at ? conversation.created_at.slice(0, 10) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}

        {pagination && pagination.total > pagination.page_size ? (
          <nav className="ws-pager" aria-label="Pagination">
            <button type="button" className="ws-btn" disabled={pagination.page <= 1} onClick={() => setPage((p) => p - 1)}>
              Previous
            </button>
            <span className="ws-mono">
              Page {pagination.page} of {Math.ceil(pagination.total / pagination.page_size)}
            </span>
            <button
              type="button"
              className="ws-btn"
              disabled={pagination.page * pagination.page_size >= pagination.total}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </button>
          </nav>
        ) : null}
      </div>
    </>
  );
}

function AskHistoryPageInner() {
  const conversationId = useSearchParams().get("id");
  return conversationId ? (
    <ConversationView key={conversationId} conversationId={conversationId} />
  ) : (
    <AskHistoryListView />
  );
}

export default function AskHistoryPage() {
  return (
    <Suspense fallback={null}>
      <AskHistoryPageInner />
    </Suspense>
  );
}
