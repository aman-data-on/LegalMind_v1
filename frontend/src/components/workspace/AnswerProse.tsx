"use client";

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
 */
export function AnswerProse({ text }: { text: string }) {
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
                <li key={item}>{line.replace(/^([-*•]|\d+[.)])\s+/, "")}</li>
              ))}
            </ul>
          );
        }
        return (
          <p key={index} className="ws-ask__text">
            {lines.join(" ")}
          </p>
        );
      })}
    </>
  );
}
