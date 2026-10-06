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
      .toBe("Could not be read (OCR_REQUIRED)");
    expect(statusText(item({ status: "UNAVAILABLE" }))).toBe("No longer available");
  });

  it("lists files by name and a paste as pasted text, with no controls", () => {
    const html = renderToStaticMarkup(<MaterialList items={[
      item({ id: "a", filename: "renewal.txt" }),
      item({ id: "b", kind: "PASTE", filename: null, status: "FAILED", failure_code: "NO_TEXT" }),
    ]} />);
    expect(html).toContain("renewal.txt");
    expect(html).toContain("Pasted text");
    expect(html).toContain("Could not be read (NO_TEXT)");
    expect(html).toContain('aria-label="Material in this chat"');
    expect(html).not.toContain("<button");          // read-only
    expect(html).not.toMatch(/confiden|probab|likely/i);
  });

  it("renders nothing for a chat with no material", () => {
    expect(renderToStaticMarkup(<MaterialList items={[]} />)).toBe("");
  });
});
