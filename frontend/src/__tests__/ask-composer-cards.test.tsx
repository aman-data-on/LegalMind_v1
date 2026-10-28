/** AM-226 (2026-10-28): files as cards, the chat's saved files as one pill, each model's
 *  state in plain words (no cause for ordinary readers, AM-222 r2/r3), and a paused model
 *  offering the one that can answer. */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { AttachmentCards, fileSize, refusalText, SentFiles } from "@/components/workspace/AttachmentCards";
import { materialSummary, MaterialList } from "@/components/workspace/ChatMaterial";
import { modelNote, PausedNotice, usable } from "@/components/workspace/ModelPicker";
import type { AskModel, ChatAttachment } from "@/lib/types";

const pdf = new File(["x".repeat(2048)], "lspl2-2026-final.pdf", { type: "application/pdf" });
const jpg = new File(["x"], "Scanned PO.jpg", { type: "image/jpeg" });

function saved(over: Partial<ChatAttachment>): ChatAttachment {
  return { id: "a1", kind: "FILE", filename: "note.txt", mime_type: "text/plain",
           byte_size: 10, status: "READY", failure_code: null,
           created_at: "2026-10-01T00:00:00Z", expires_at: "2026-10-31T00:00:00Z", ...over };
}

const gemini: AskModel = { id: "gemini", label: "Gemini", default: true, configured: true };
const together: AskModel = { id: "together-deepseek", label: "DeepSeek (Together)", default: false, configured: true };

describe("attachment cards", () => {
  it("shows each file's type and size, and why a file cannot be sent, on its own card", () => {
    const html = renderToStaticMarkup(<AttachmentCards onRemove={() => undefined} files={[
      { key: "1", file: pdf, problem: null },
      { key: "2", file: jpg, problem: "use PDF, Word, Markdown or text" },
    ]} />);
    expect(html).toContain('aria-label="Files to send"');
    expect(html).toContain(">PDF<");
    expect(html).toContain("PDF, 2 KB");
    expect(html).toContain("Not sent: use PDF, Word, Markdown or text");
    expect(html).toContain('aria-label="Remove Scanned PO.jpg"');
    expect(html.match(/<button/g)).toHaveLength(2);    // one remove control per card
  });

  it("fixes the cards while they are sent: a removed card would still be uploaded", () => {
    const html = renderToStaticMarkup(<AttachmentCards disabled onRemove={() => undefined}
                                                       files={[{ key: "1", file: pdf, problem: null }]} />);
    expect(html).toContain("disabled");
  });

  it("renders nothing with no files, and sizes read as people say them", () => {
    expect(renderToStaticMarkup(<AttachmentCards files={[]} onRemove={() => undefined} />)).toBe("");
    expect(fileSize(100)).toBe("1 KB");
    expect(fileSize(2.4 * 1024 * 1024)).toBe("2.4 MB");
  });
});

describe("the files a question was sent with", () => {
  it("are read-only cards above it, and a file not read whole says so", () => {
    const html = renderToStaticMarkup(<SentFiles files={[
      saved({ id: "a", filename: "renewal.pdf", byte_size: 2048 }),
      saved({ id: "b", kind: "PASTE", filename: null }),
      saved({ id: "c", filename: "scan.pdf", status: "FAILED", failure_code: "OCR_REQUIRED" }),
    ]} />);
    expect(html).toContain('aria-label="Files sent with this question"');
    expect(html).toContain("renewal.pdf");
    expect(html).toContain("PDF, 2 KB");
    expect(html).toContain("Pasted text");
    expect(html).toContain("Scanned — not readable here");
    expect(html).not.toContain("<button");                     // nothing to remove once sent
    expect(renderToStaticMarkup(<SentFiles files={[]} />)).toBe("");
  });
});

describe("a file the server refuses", () => {
  it("is said in plain words on its card, never as the raw code", () => {
    expect(refusalText(new Error("the attachment was refused: UNRECOGNISED_CONTENT")))
      .toBe("its content is not a readable PDF, Word or text file");
    expect(refusalText(new Error("the attachment was refused: SOMETHING_NEW")))
      .toBe("the server could not take this file");
    expect(refusalText(new Error("Network error"))).toBeNull();   // the log reports it
  });
});

describe("the chat's saved files", () => {
  it("is one pill that opens to the list, and counts what needs attention", () => {
    const items = [saved({ id: "a" }), saved({ id: "b", status: "FAILED", failure_code: "NO_TEXT" }),
                   saved({ id: "c", status: "PROCESSING" })];
    expect(materialSummary(items)).toBe("3 files in this chat, 1 could not be read, 1 being read");
    expect(materialSummary([saved({})])).toBe("1 file in this chat");
    // the pill's words match its attention style: a file read in part is said (review)
    expect(materialSummary([{ ...saved({}), pages_unread: [4, 5] }])).toBe("1 file in this chat, 1 read in part");
    const html = renderToStaticMarkup(<MaterialList items={items} />);
    expect(html).toMatch(/^<details class="ws-chat__saved" data-attention="">/);
    expect(html).toContain("<summary>");
  });
});

describe("model states", () => {
  it("says each state in plain words, never the cause", () => {
    expect(modelNote({ ...gemini, paused: true })).toBe("Paused. Try another model.");
    expect(modelNote({ ...together, configured: false })).toBe("Not available right now");
    expect(modelNote(gemini)).toBe("Default");
    expect(modelNote(together)).toBe("Available");
    expect(usable({ ...gemini, paused: true })).toBe(false);
  });

  it("offers the model that can answer when the chosen one is paused", () => {
    const html = renderToStaticMarkup(
      <PausedNotice model={{ ...gemini, paused: true }} fallback={together} onSwitch={() => undefined} />);
    expect(html).toContain("Gemini is paused right now");
    expect(html).toContain("Switch to DeepSeek (Together)");
    expect(html).not.toMatch(/credit|billing|payment|quota|402/i);
  });

  it("offers the switch for a model that is not configured, too", () => {
    const html = renderToStaticMarkup(<PausedNotice model={{ ...together, configured: false }}
                                                    fallback={gemini} onSwitch={() => undefined} />);
    expect(html).toContain("DeepSeek (Together) is not available right now");
    expect(html).toContain("Switch to Gemini");
  });

  it("keeps AM-222's wording when no model can answer", () => {
    const html = renderToStaticMarkup(<PausedNotice model={{ ...gemini, paused: true }} fallback={null} />);
    expect(html).toContain("AI answers are paused");
    expect(html).not.toContain("Switch to");
  });
});
