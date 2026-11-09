/**
 * A row's text cut into prose and TABLES (N11 #1, 2026-11-09). The parser writes every
 * table row as one `| a | b |` line (`parsing.table_row`, 34.9) and a nested table inside a
 * cell as `[a | b; c | d]`; the text view sets those lines as a table instead of pipe text.
 * Presentation only: the evidence string is unchanged, nothing is re-extracted (`AM-57`).
 */
export interface TableCell {
  text: string;
  /** Where the cell's text starts in the row's content: a reader's highlight (offsets
   *  into the content) is drawn in its cell. -1 when not found. */
  start: number;
  /** A table inside this cell, row by row, and where each inner cell starts. */
  nested?: string[][];
  nestedStart?: number[][];
  /** Columns this cell covers: a row with fewer cells than the widest (a merged label,
   *  "Grand total") stretches its FIRST cell — Word merges a totals label leftwards. */
  span: number;
}
export type TextBlock = { kind: "text"; text: string; start: number } | { kind: "table"; rows: TableCell[][] };

const ROW = /^\| .*\|$/;

/** `a | b | [x | y; z | w]` split at the separators outside any bracket. */
function splitTop(text: string, separator: string): string[] {
  const out: string[] = [];
  let depth = 0;
  let start = 0;
  for (let i = 0; i < text.length; i += 1) {
    const c = text[i];
    if (c === "[") depth += 1;
    else if (c === "]") depth = Math.max(0, depth - 1);
    else if (depth === 0 && text.startsWith(separator, i)) {
      out.push(text.slice(start, i));
      start = i + separator.length;
      i += separator.length - 1;
    }
  }
  out.push(text.slice(start));
  return out.map((cell) => cell.trim());
}

/** Each of ``parts`` located in ``content`` in order from ``from`` (-1 when absent). */
function locate(content: string, parts: string[], from: number): number[] {
  let at = from;
  return parts.map((part) => {
    const found = content.indexOf(part, at);
    if (found >= 0) at = found + part.length;
    return found;
  });
}

function cell(text: string, start: number, content: string): TableCell {
  const inner = /^\[(.*)\]$/.exec(text)?.[1];
  if (inner === undefined || !inner.includes(" | ")) return { text, start, span: 1 };
  const nested = splitTop(inner, "; ").map((row) => splitTop(row, " | "));
  let from = Math.max(0, start);
  const nestedStart = nested.map((row) => {
    const at = locate(content, row, from);
    from = Math.max(from, ...at.map((a, i) => (a >= 0 ? a + row[i]!.length : 0)));
    return at;
  });
  return { text, start, nested, nestedStart, span: 1 };
}

export function tableCells(line: string, content = line, lineStart = 0): TableCell[] {
  const texts = splitTop(line.replace(/^\|\s?/, "").replace(/\s?\|$/, ""), " | ");
  const starts = locate(content, texts, lineStart);
  return texts.map((text, i) => cell(text, starts[i]!, content));
}

export function textBlocks(content: string): TextBlock[] {
  const blocks: TextBlock[] = [];
  let at = 0;
  for (const line of content.split("\n")) {
    const last = blocks[blocks.length - 1];
    if (ROW.test(line.trim())) {
      const row = tableCells(line.trim(), content, at);
      if (last?.kind === "table") last.rows.push(row);
      else blocks.push({ kind: "table", rows: [row] });
    } else if (last?.kind === "text") {
      last.text += `\n${line}`;
    } else {
      blocks.push({ kind: "text", text: line, start: at });
    }
    at += line.length + 1;
  }
  for (const block of blocks) {
    if (block.kind !== "table") continue;
    const width = Math.max(...block.rows.map((row) => row.length));
    for (const row of block.rows) row[0]!.span = width - row.length + 1;
  }
  return blocks;
}

export function hasTable(content: string): boolean {
  return content.split("\n").some((line) => ROW.test(line.trim()));
}

/** A figure ("₹ 6,000.00", "18%", "37") — kept on one line in its cell. */
export function isFigure(text: string): boolean {
  return /^[₹$€£]?\s?[\d,.\s]+%?$/.test(text.trim());
}
