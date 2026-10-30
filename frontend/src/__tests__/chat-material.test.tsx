/**
 * Ask plan 1.2 — the chat's material and its status, read-only (owner UI exception,
 * 2026-10-01). Status is a word, never colour alone; a paste has no filename.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { MaterialList, statusText } from "@/components/workspace/ChatMaterial";
import type { ChatAttachment } from "@/lib/types";

function item(over: Partial<ChatAttachment>): ChatAttachment {
  return { id: "a1", kind: "FILE", filename: "note.txt", mime_type: "text/plain",
           byte_size: 10, status: "READY", failure_code: null,
           created_at: "2026-10-01T00:00:00Z", expires_at: "2026-10-31T00:00:00Z", ...over };
}

describe("chat material", () => {
  it("states every status in words", () => {
    expect(statusText(item({ status: "PROCESSING" }))).toBe("Processing");
    expect(statusText(item({ status: "READY" }))).toBe("Ready");
    expect(statusText(item({ status: "FAILED", failure_code: "OCR_REQUIRED" })))
      .toBe("Scanned — not readable here. Upload it on the Dashboard, where scans are read.");
    // every failure in words with what to do next, never a code (Ask audit H5)
    expect(statusText(item({ status: "FAILED", failure_code: "NO_TEXT" })))
      .toMatch(/^No readable text found — .* Paste its text here, or upload it on the Dashboard/);
    expect(statusText(item({ status: "FAILED", failure_code: "SOMETHING_NEW" })))
      .not.toMatch(/[A-Z]{2,}_[A-Z]/);
    // QA-037: a password, a macro file, a damaged file — each said as itself
    expect(statusText(item({ status: "FAILED", failure_code: "PASSWORD_PROTECTED" })))
      .toMatch(/^This PDF is password-protected\./);
    expect(statusText(item({ status: "FAILED", failure_code: "MACRO_ENABLED" })))
      .toMatch(/macro-enabled Word file/);
    expect(statusText(item({ status: "UNAVAILABLE" }))).toBe("No longer available");
    // F7: a file read in part says which pages were not read, never a plain "Ready"
    expect(statusText({ ...item({}), pages_unread: [3] })).toBe("Ready — page 3 could not be read");
    expect(statusText({ ...item({}), pages_unread: [2, 5] }))
      .toBe("Ready — pages 2, 5 could not be read");
    // a long scan over the OCR bound: counted, never a hundred page numbers
    expect(statusText({ ...item({}), pages_unread: Array.from({ length: 40 }, (_, i) => i + 21) }))
      .toBe("Ready — 40 pages could not be read");
  });

  it("lists files by name and a paste as pasted text, with no controls", () => {
    const html = renderToStaticMarkup(<MaterialList items={[
      item({ id: "a", filename: "renewal.txt" }),
      item({ id: "b", kind: "PASTE", filename: null, status: "FAILED", failure_code: "NO_TEXT" }),
    ]} />);
    expect(html).toContain("renewal.txt");
    expect(html).toContain("Pasted text");
    expect(html).toContain("Nothing to read in this pasted text. Paste it again.");
    expect(html).toContain('aria-label="Material in this chat"');
    expect(html).not.toContain("<button");          // read-only
    expect(html).not.toMatch(/confiden|probab|likely/i);
  });

  it("renders nothing for a chat with no material", () => {
    expect(renderToStaticMarkup(<MaterialList items={[]} />)).toBe("");
  });
});
