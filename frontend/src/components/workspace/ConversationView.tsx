"use client";

/**
 * One recorded Ask conversation — P1 (PRODUCT_UX_ROADMAP §E screen 9). A saved
 * record, read-only: every answer replays with the SAME citations it carried
 * live (`AM-25` r5), each one a real link into the document workspace's
 * highlight. Asking continues in the workspace, not here — one place to ask,
 * one place to reread.
 *
 * Denial semantics: someone else's conversation and a nonexistent one read
 * identically — "Not found." (`AM-25` r7 applied to the assist lane).
 */

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { ApiError, api, describeError } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { ConversationDetail } from "@/lib/types";

import { TranscriptTurn } from "./TranscriptTurn";

type Load =
  | { kind: "loading" }
  | { kind: "ready"; conversation: ConversationDetail; contractName: string | null }
  | { kind: "error"; error: unknown };

export function ConversationView({ conversationId }: { conversationId: string }) {
  const { can } = useSession();
  const [state, setState] = useState<Load>({ kind: "loading" });

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const conversation = await api.conversation(conversationId);
      let contractName: string | null = null;
      if (conversation.contract_id) {
        try {
          contractName = (await api.contract(conversation.contract_id)).name;
        } catch {
          contractName = null;
        }
      }
      setState({ kind: "ready", conversation, contractName });
    } catch (error) {
      setState({ kind: "error", error });
    }
  }, [conversationId]);

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

  if (state.kind === "loading") {
    return (
      <div className="ws-state" aria-busy="true">
        <p className="ws-visually-hidden" role="status" aria-live="polite">
          Loading the conversation…
        </p>
        <span className="ws-skel ws-skel--line" style={{ width: "45%", height: "1.2rem" }} aria-hidden="true" />
        <span className="ws-skel ws-skel--line" style={{ width: "70%" }} aria-hidden="true" />
      </div>
    );
  }

  if (state.kind === "error") {
    const notFound = state.error instanceof ApiError && state.error.isNotFound;
    return (
      <div className={`ws-state${notFound ? "" : " ws-state--error"}`} role={notFound ? "note" : "alert"}>
        <h2>{notFound ? "Not found." : "The conversation could not be loaded."}</h2>
        {notFound ? (
          <p>
            <Link href="/workspace/ask">Back to ask history</Link>
          </p>
        ) : (
          <p>{describeError(state.error)}</p>
        )}
      </div>
    );
  }

  const { conversation, contractName } = state;

  return (
    <>
      <div className="ws-context">
        <h1>Ask history</h1>
        <div className="ws-context__meta">
          {conversation.contract_id ? (
            <Link href={`/workspace/${conversation.contract_id}`}>
              {contractName ?? "Open the workspace"}
            </Link>
          ) : (
            <span className="ws-pane__note">not scoped to a document</span>
          )}
        </div>
      </div>
      <div className="ws-transcript">
        <p className="ws-pane__note">
          A saved record — every answer replays with the citations it carried live. To ask
          something new, open the document&rsquo;s workspace.
        </p>
        {conversation.messages.length === 0 ? (
          <div className="ws-state">
            <h2>Nothing asked yet.</h2>
            <p>This conversation was opened but no question was sent.</p>
          </div>
        ) : (
          conversation.messages.map((turn) => (
            <TranscriptTurn key={turn.id} turn={turn} contractId={conversation.contract_id} />
          ))
        )}
      </div>
    </>
  );
}
