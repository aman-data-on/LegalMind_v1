"use client";

import type { ReactNode } from "react";

/**
 * The answer, as paragraphs and bullets — owner request, 2026-09-11 ("proper
 * paragraph spacing, bullets when useful").
 *
 * Deliberately NOT a markdown renderer: the generator's output is prose over
 * retrieved passages, and a parser that invented headings, links or emphasis from
 * stray punctuation would be putting formatting into a legal answer that nobody
 * wrote. Blank lines separate paragraphs; a run of lines opening with a bullet or a
 * number becomes a list. Nothing else is interpreted, and every character of the
 * original text survives.
 *
 * Extracted from `TranscriptTurn` (2026-09-15) so the live dock can use it too. It
 * rendered `result.text` in a single flat `<p>`, so the SAME answer was laid out one
 * way while being read and another way on reload — paragraphs collapsed into a wall.
 * `TranscriptTurn` already imports from `AskDock`, so the dock could not import back
 * without a cycle; a module both can depend on is the smaller fix.
 *
 * ── Citation markers (Ask target architecture Phase 3, 2026-09-17) ──────────────
 * The generator cites its evidence as `[n]`, and `n` indexes the source list rendered
 * under the answer — the server renumbers prose and list into one sequence AFTER
 * verification (`service._renumber_markers`, PR #68). Until now both halves were
 * inert text, so a reader on the fourth point of an answer had to count list items to
 * find source 4. Given `citeCount` and `citeTargetId`, a marker in range becomes a
 * reference that moves focus to its own source; everything else — an out-of-range
 * number, a bracketed aside the model wrote, a bare `[`, the whole of a turn rendered
 * without the two props — stays exactly the literal text it is today.
 *
 * It is a NAVIGATION aid and nothing more. It does not restate, score or qualify the
 * evidence: no count, no strength, no "primary source", nothing that could read as
 * confidence in the claim (rule 12, DESIGN.md). The marker says where to look.
 */

/** `[1]`, `[12]` — one or more digits, nothing else. A marker the model wrote around
 *  anything but digits (`[see §7]`) is not a citation and is left alone. Split keeps
 *  the captured group, so every character of the original survives the round trip. */
const MARKER = /(\[\d+\])/g;

export function AnswerProse({
  text,
  citeCount = 0,
  citeTargetId,
}: {
  text: string;
  /** How many sources the answer actually carries. A marker above this is left as
   *  text: it points at nothing, and a reference that goes nowhere is worse than a
   *  number. */
  citeCount?: number;
  /** Builds the DOM id of source `n` — the same function the source list uses, so
   *  the two cannot drift. Absent (a turn with no source list, a refusal, the
   *  transcript before it opts in) means markers stay literal. */
  citeTargetId?: ((n: number) => string) | undefined;
}) {
  const blocks = text.split(/\n{2,}/).filter((block) => block.trim().length > 0);
  return (
    <>
      {blocks.map((block, index) => {
        const lines = block.split("\n").map((line) => line.trim()).filter(Boolean);
        const bullets = lines.every((line) => /^([-*•]|\d+[.)])\s+/.test(line));
        if (bullets && lines.length > 1) {
          return (
            <ul key={index} className="ws-ask__bullets">
              {lines.map((line, item) => (
                <li key={item}>
                  {withMarkers(line.replace(/^([-*•]|\d+[.)])\s+/, ""), citeCount, citeTargetId)}
                </li>
              ))}
            </ul>
          );
        }
        return (
          <p key={index} className="ws-ask__text">
            {withMarkers(lines.join(" "), citeCount, citeTargetId)}
          </p>
        );
      })}
    </>
  );
}

/** The prose of one paragraph or bullet, with in-range `[n]` markers turned into
 *  references. Returns the plain string when there is nothing to link, so the common
 *  case (no sources, or no target function) allocates nothing and renders exactly as
 *  it did before this existed. */
function withMarkers(
  line: string,
  citeCount: number,
  citeTargetId?: (n: number) => string,
): ReactNode {
  if (!citeTargetId || citeCount < 1 || !line.includes("[")) return line;
  const parts = line.split(MARKER);
  if (parts.length === 1) return line;
  return parts.map((part, index) => {
    const match = /^\[(\d+)\]$/.exec(part);
    const n = match ? Number(match[1]) : 0;
    if (n < 1 || n > citeCount) return part;
    return <CiteRef key={index} n={n} targetId={citeTargetId(n)} />;
  });
}

/** One marker, as a reference to its source.
 *
 *  A button rather than an `<a href="#…">`: the anchor form would push a hash onto a
 *  URL that already carries the workspace's document, version and evidence state, and
 *  a back button that undid a footnote jump instead of the document you opened is the
 *  wrong behaviour. Focus moves to the source (not just the scroll position), so the
 *  jump works for a keyboard and a screen reader and not only for a mouse — the
 *  source list item is focusable for exactly this reason.
 *
 *  Inline in a sentence, so WCAG 2.2 Target Size (Minimum) applies its in-text
 *  exception; the padding is for comfort, and deliberately not enough to break the
 *  line rhythm of a paragraph of legal prose.
 */
function CiteRef({ n, targetId }: { n: number; targetId: string }) {
  return (
    <button
      type="button"
      className="ws-ask__ref ws-mono"
      /* "Source 4", not "Citation 4" or "Reference 4": the list it points at is
         headed "Sources", and one word for one thing across the interface. */
      aria-label={`Go to source ${n}`}
      onClick={() => {
        const target = typeof document === "undefined" ? null : document.getElementById(targetId);
        if (!target) return;
        target.scrollIntoView({ block: "nearest", behavior: "smooth" });
        /* The item carries tabIndex={-1}; focusing it is what announces the source
           to a screen reader and gives the eye somewhere to land. `preventScroll`
           leaves the smooth scroll above in charge of the movement. */
        target.focus({ preventScroll: true });
      }}
    >
      [{n}]
    </button>
  );
}
