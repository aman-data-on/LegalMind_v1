"use client";

/**
 * The chat's own material and its status — Ask plan 1.2, the owner's approved UI
 * exception (2026-10-01, DECISIONS A-27). READ-ONLY: nothing here adds, removes or
 * retries; it states what the server holds for this conversation.
 *
 * Status is written as a word, never shown by colour alone. The list renders nothing
 * when the chat holds no material — and when attachments are switched off, because
 * the server then refuses the request and that is read as "none".
 */
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { ChatAttachment } from "@/lib/types";

import { IconFile } from "./icons";

const STATUS: Record<ChatAttachment["status"], string> = {
  PROCESSING: "Processing",
  READY: "Ready",
  FAILED: "Could not be read",
  UNAVAILABLE: "No longer available",
};

export function statusText(a: ChatAttachment): string {
  return a.status === "FAILED" && a.failure_code
    ? `${STATUS.FAILED} (${a.failure_code})`
    : STATUS[a.status];
}

export function ChatMaterial({ conversationId, refresh }: {
  conversationId: string | null;
  /** Bumped after each answer, so a paste saved by that turn appears. */
  refresh: number;
}) {
  const [items, setItems] = useState<ChatAttachment[]>([]);
  useEffect(() => {
    let cancelled = false;
    if (!conversationId) {
      setItems([]);
      return;
    }
    api.attachments(conversationId)
      .then((rows) => { if (!cancelled) setItems(rows); })
      .catch(() => { if (!cancelled) setItems([]); });
    return () => { cancelled = true; };
  }, [conversationId, refresh]);

  return <MaterialList items={items} />;
}

/** The list itself, pure — rendered to static markup in tests (Step 39). */
export function MaterialList({ items }: { items: ChatAttachment[] }) {
  if (items.length === 0) return null;
  return (
    <ul className="ws-chat__files ws-chat__material" aria-label="Material in this chat">
      {items.map((a) => (
        <li key={a.id} className="ws-chat__file" data-status={a.status}>
          <IconFile size={13} />
          <span className="ws-chat__filename">{a.filename ?? "Pasted text"}</span>
          <span className="ws-chat__filestatus">{statusText(a)}</span>
        </li>
      ))}
    </ul>
  );
}
