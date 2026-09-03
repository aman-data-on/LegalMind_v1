"use client";

/**
 * Reader annotations — select text in the document, mark it, optionally note
 * why (owner request, 2026-09-02; DD-14).
 *
 * These are PERSONAL READING MARKS, and three boundaries keep them that way:
 *
 *  1. They are presentation only. An annotation never touches a Finding, an
 *     Evaluation, a Decision or any legal table (rule 18 — the UI implements
 *     no legal logic); it is a span of the reader's own attention.
 *  2. They live in THIS BROWSER's localStorage, keyed by document version —
 *     no endpoint exists for them, and inventing one would be a schema
 *     decision the specification has not made (rule 4). The UI says
 *     "on this device" so localStorage never masquerades as the system of
 *     record.
 *  3. They anchor to an evidence row id + character offsets INTO that row's
 *     unmodified content, so they can never survive re-extraction of a
 *     different version — each version keeps its own set.
 */

import { useCallback, useEffect, useState } from "react";

export interface Annotation {
  id: string;
  rowId: string;
  /** Character offsets into the row's `content`, [start, end). */
  start: number;
  end: number;
  note: string;
  created: string;
}

const key = (versionId: string) => `legalmind.annotations.${versionId}`;

function load(versionId: string): Annotation[] {
  try {
    const raw = window.localStorage.getItem(key(versionId));
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (a): a is Annotation =>
        typeof a === "object" && a !== null &&
        typeof (a as Annotation).rowId === "string" &&
        typeof (a as Annotation).start === "number" &&
        typeof (a as Annotation).end === "number" &&
        (a as Annotation).end > (a as Annotation).start,
    );
  } catch {
    // Private windows / blocked storage: annotations simply don't persist.
    return [];
  }
}

function save(versionId: string, annotations: Annotation[]) {
  try {
    window.localStorage.setItem(key(versionId), JSON.stringify(annotations));
  } catch {
    // Best-effort — the in-memory copy still renders for this session.
  }
}

export function useAnnotations(versionId: string) {
  const [annotations, setAnnotations] = useState<Annotation[]>([]);

  useEffect(() => {
    setAnnotations(load(versionId));
  }, [versionId]);

  const add = useCallback(
    (rowId: string, start: number, end: number): Annotation => {
      const annotation: Annotation = {
        id: `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
        rowId, start, end, note: "",
        created: new Date().toISOString(),
      };
      setAnnotations((current) => {
        const next = [...current, annotation];
        save(versionId, next);
        return next;
      });
      return annotation;
    },
    [versionId],
  );

  const remove = useCallback(
    (id: string) => {
      setAnnotations((current) => {
        const next = current.filter((a) => a.id !== id);
        save(versionId, next);
        return next;
      });
    },
    [versionId],
  );

  const setNote = useCallback(
    (id: string, note: string) => {
      setAnnotations((current) => {
        const next = current.map((a) => (a.id === id ? { ...a, note } : a));
        save(versionId, next);
        return next;
      });
    },
    [versionId],
  );

  return { annotations, add, remove, setNote };
}

/** One run of a row's text: marked by an annotation, or plain. */
export interface Segment {
  text: string;
  annotation: Annotation | null;
}

/**
 * Split a row's UNMODIFIED content into plain/marked runs. Overlaps resolve to
 * whichever annotation starts first (marks split, text never duplicates or
 * drops — the concatenation of segments is always exactly `content`).
 */
export function segmentContent(content: string, annotations: Annotation[]): Segment[] {
  const inRange = annotations
    .map((a) => ({
      ...a,
      start: Math.max(0, Math.min(a.start, content.length)),
      end: Math.max(0, Math.min(a.end, content.length)),
    }))
    .filter((a) => a.end > a.start)
    .sort((a, b) => a.start - b.start || a.end - b.end);
  const segments: Segment[] = [];
  let at = 0;
  for (const a of inRange) {
    if (a.end <= at) continue; // fully inside an earlier mark
    const start = Math.max(a.start, at);
    if (start > at) segments.push({ text: content.slice(at, start), annotation: null });
    segments.push({ text: content.slice(start, a.end), annotation: a });
    at = a.end;
  }
  if (at < content.length) segments.push({ text: content.slice(at), annotation: null });
  return segments.length > 0 ? segments : [{ text: content, annotation: null }];
}

/**
 * The reader's selection, resolved to (rowId, offsets) — or null when it is
 * not usable: empty, crossing rows, or touching anything but the row text.
 * Offsets are measured against the row `<p>`'s full text content, which IS the
 * unmodified evidence string (segments only ever re-wrap it).
 */
export function selectionInRow(selection: Selection | null): {
  rowId: string; start: number; end: number;
} | null {
  if (!selection || selection.isCollapsed || selection.rangeCount === 0) return null;
  const range = selection.getRangeAt(0);
  const owner = (node: Node | null): HTMLElement | null => {
    for (let n = node; n; n = n.parentNode) {
      if (n instanceof HTMLElement && n.matches("p.ws-row__text")) return n;
    }
    return null;
  };
  const startP = owner(range.startContainer);
  if (!startP || owner(range.endContainer) !== startP) return null;
  const rowId = startP.closest("[data-evidence-id]")?.getAttribute("data-evidence-id");
  if (!rowId) return null;
  // Offset of the range start within the paragraph = length of the text
  // between the paragraph's start and the selection's start.
  const prefix = document.createRange();
  prefix.selectNodeContents(startP);
  prefix.setEnd(range.startContainer, range.startOffset);
  const start = prefix.toString().length;
  const end = start + range.toString().length;
  if (end <= start) return null;
  return { rowId, start, end };
}
