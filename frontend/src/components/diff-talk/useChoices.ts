import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api, describeError } from "@/lib/api";
import type { ComparisonChoice } from "@/lib/types";
import type { Choice } from "./text";

/**
 * The drafting choices for one pair of documents, kept by LegalMind (AB-81 / AM-136):
 * the same on every device, shared with everyone who can read both documents, last
 * writer wins. Only the owner of every stored side may change them (`canChoose`).
 *
 * - A click shows at once and saves in the background; the server's answer is the
 *   truth, and only the NEWEST answer is applied — two quick clicks never let the
 *   first one's late reply undo the second.
 * - A failed save reloads what is stored and says so: nothing looks kept that is not.
 * - Choices made before this, in this browser only, are brought over once — when the
 *   reader may choose and the pair has none stored yet — then cleared here.
 */
export function useChoices(left: string, right: string) {
  const [byKey, setByKey] = useState<Record<string, ComparisonChoice>>({});
  const [canChoose, setCanChoose] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const latest = useRef(0);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const stored = await api.comparisonChoices(left, right);
        let choices = stored.choices;
        const local = readLocal(left, right);
        if (stored.can_choose && !Object.keys(choices).length && Object.keys(local).length) {
          choices = await api.setComparisonChoices(left, right, local);
          clearLocal(left, right);
        }
        if (cancelled) return;
        setByKey(choices);
        setCanChoose(stored.can_choose);
      } catch (e) {
        if (!cancelled) setError(`Choices could not be loaded — ${describeError(e)}`);
      } finally {
        if (!cancelled) setLoaded(true);
      }
    })();
    return () => { cancelled = true; };
  }, [left, right]);

  const choose = useCallback((key: string, choice: Choice) => {
    const request = ++latest.current;
    setError(null);
    setByKey((now) => ({ ...now, [key]: {
      choice, decided_by: "", decided_by_me: true, updated_at: new Date().toISOString() } }));
    api.setComparisonChoices(left, right, { [key]: choice })
      .then((stored) => { if (request === latest.current) setByKey(stored); })
      .catch((e: unknown) => {
        setError(`Your choice was not saved — ${describeError(e)}`);
        // Show what is really stored, not what the click hoped for.
        api.comparisonChoices(left, right).then((s) => setByKey(s.choices)).catch(() => undefined);
      });
  }, [left, right]);

  const choices = useMemo(
    () => Object.fromEntries(Object.entries(byKey).map(([k, v]) => [k, v.choice])) as Record<string, Choice>,
    [byKey]);
  return { choices, byKey, canChoose, loaded, error, choose };
}

// The browser-only store this replaced (2026-10-13), read once to bring choices over.
const localKey = (left: string, right: string) => `diff-talk:choices:v2:${left}|${right}`;

function readLocal(left: string, right: string): Record<string, Choice> {
  try {
    const raw: unknown = JSON.parse(window.localStorage.getItem(localKey(left, right)) ?? "{}");
    if (!raw || typeof raw !== "object") return {};
    return Object.fromEntries(Object.entries(raw)
      .filter(([, v]) => v === "ours" || v === "theirs")) as Record<string, Choice>;
  } catch {
    return {};
  }
}

function clearLocal(left: string, right: string) {
  try { window.localStorage.removeItem(localKey(left, right)); } catch { /* none */ }
}
