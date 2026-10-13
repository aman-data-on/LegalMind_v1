import { useEffect, useState } from "react";

import type { Choice } from "./text";

/**
 * The reader's choices for one pair of documents, kept in THIS browser.
 * ponytail: browser-only — a cleared browser or another laptop loses them, and a
 * colleague cannot see them; server-side saving waits on the owner (one new table).
 * Storage may be absent (private window) or hold anything — read defensively.
 */
export function useChoices(left: string, right: string) {
  const key = `diff-talk:choices:v2:${left}|${right}`;
  const [choices, setChoices] = useState<Record<string, Choice>>(() => read(key));
  useEffect(() => {
    try { window.localStorage.setItem(key, JSON.stringify(choices)); } catch { /* none */ }
  }, [key, choices]);
  return [choices, setChoices] as const;
}

function read(key: string): Record<string, Choice> {
  try {
    const raw: unknown = JSON.parse(window.localStorage.getItem(key) ?? "{}");
    if (!raw || typeof raw !== "object") return {};
    return Object.fromEntries(Object.entries(raw)
      .filter(([, v]) => v === "ours" || v === "theirs")) as Record<string, Choice>;
  } catch {
    return {};
  }
}
