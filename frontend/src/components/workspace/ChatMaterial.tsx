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

import { IconChevronDown, IconFile, IconPaperclip } from "./icons";

const STATUS: Record<ChatAttachment["status"], string> = {
  PROCESSING: "Processing",
  READY: "Ready",
  FAILED: "Could not be read",
  UNAVAILABLE: "No longer available",
};

/** A scan has no text layer; chat material is OCR'd only up to a short page bound (F7),
 *  the Dashboard upload always (`AM-133`), so the reader is told where it can be read. */
const SCANNED = "Scanned — not readable here. Upload it on the Dashboard, where scans are read.";

/** `pages_unread`: a READY file read in part (F7) — said, never shown as plain "Ready". */
export function statusText(a: ChatAttachment): string {
  const unread = a.status === "READY" ? a.pages_unread ?? [] : [];
  if (unread.length) {
    // a long scan over the OCR bound can leave dozens unread: counted, not listed
    const which = unread.length > 8 ? `${unread.length} pages`
      : `page${unread.length > 1 ? "s" : ""} ${unread.join(", ")}`;
    return `${STATUS.READY} — ${which} could not be read`;
  }
  if (a.status !== "FAILED" || !a.failure_code) return STATUS[a.status];
  return a.failure_code === "OCR_REQUIRED" ? SCANNED : `${STATUS.FAILED} (${a.failure_code})`;
}

export function ChatMaterial({ conversationId, refresh, onCount }: {
  conversationId: string | null;
  /** Bumped after each answer, so a paste saved by that turn appears. */
  refresh: number;
  /** How many files the chat holds, for the composer's 10-file cap. */
  onCount?: (count: number) => void;
}) {
  const [items, setItems] = useState<ChatAttachment[]>([]);
  useEffect(() => {
    let cancelled = false;
    if (!conversationId) {
      setItems([]);
      onCount?.(0);
      return;
    }
    api.attachments(conversationId)
      .then((rows) => { if (!cancelled) { setItems(rows); onCount?.(rows.length); } })
      .catch(() => { if (!cancelled) setItems([]); });
    return () => { cancelled = true; };
  }, [conversationId, refresh, onCount]);

  return <MaterialList items={items} />;
}

/** "3 files in this chat", and how many need the reader's attention — said in words. */
export function materialSummary(items: ChatAttachment[]): string {
  const files = `${items.length} file${items.length === 1 ? "" : "s"} in this chat`;
  const unread = items.filter((a) => a.status === "FAILED" || a.status === "UNAVAILABLE").length;
  const reading = items.filter((a) => a.status === "PROCESSING").length;
  const partly = items.filter((a) => a.status === "READY" && (a.pages_unread ?? []).length).length;
  return [files, unread ? `${unread} could not be read` : "", partly ? `${partly} read in part` : "",
          reading ? `${reading} being read` : ""]
    .filter(Boolean).join(", ");
}

/** The list itself, pure — rendered to static markup in tests (Step 39). One pill that
 *  opens to the list (`AM-226`): the chat's files no longer fill the question box. */
export function MaterialList({ items }: { items: ChatAttachment[] }) {
  if (items.length === 0) return null;
  const attention = items.some((a) => a.status !== "READY" || (a.pages_unread ?? []).length);
  return (
    <details className="ws-chat__saved" data-attention={attention ? "" : undefined}>
      <summary>
        <IconPaperclip size={14} />
        <span>{materialSummary(items)}</span>
        <IconChevronDown size={13} />
      </summary>
      <ul className="ws-chat__material" aria-label="Material in this chat">
        {items.map((a) => (
          <li key={a.id} className="ws-chat__saveditem" data-status={a.status}>
            <IconFile size={14} />
            <span className="ws-chat__filename">{a.filename ?? "Pasted text"}</span>
            <span className="ws-chat__filestatus">{statusText(a)}</span>
          </li>
        ))}
      </ul>
    </details>
  );
}
