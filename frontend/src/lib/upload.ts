/**
 * One way to start a contract from a file, for every upload page (batch 5, review M3/S6):
 * the file's pre-check, and the chain create → upload → suggest a type → analyse. The
 * server stays the authority on every file (34.16) and every rule; these are conveniences.
 */

import { chainAnalysis } from "./analysisChain";
import { api, uploadFirstDocument, type CompareWith, type UploadRole } from "./api";
import { nameFromFilename } from "./documentTypes";

/** Mirrors the server default (`LEGALMIND_MAX_UPLOAD_BYTES`, 25 MB — owner, 2026-09-02). */
export const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;
export const UPLOAD_EXTENSIONS = [".pdf", ".docx", ".md", ".txt"];
const NAMES: Record<string, string> = { ".pdf": "PDF", ".docx": "Word", ".md": "Markdown", ".txt": "text",
                                        ".png": "PNG", ".jpg": "JPG", ".jpeg": "JPG" };

export type FileProblem = "type" | "size" | "empty";

/** What is wrong with a chosen file before it is sent, or null. */
export function fileProblem(file: File, extensions: string[], maxBytes = MAX_UPLOAD_BYTES): FileProblem | null {
  const name = file.name.toLowerCase();
  if (!extensions.some((e) => name.endsWith(e))) return "type";
  if (file.size > maxBytes) return "size";
  return file.size === 0 ? "empty" : null;
}

/** The kinds a list of extensions names, in plain words: "PDF, Word, Markdown or text". */
export function kindsOf(extensions: string[]): string {
  const kinds = [...new Set(extensions.map((e) => NAMES[e] ?? e))];
  return kinds.length > 1 ? `${kinds.slice(0, -1).join(", ")} or ${kinds.at(-1)}` : kinds[0] ?? "";
}

/** The upload pages' sentence for a file that cannot be sent, or null. */
export function preflightProblem(file: File, extensions = UPLOAD_EXTENSIONS): string | null {
  return {
    type: `This file type is not supported. Choose a ${kindsOf(extensions)} file.`,
    size: "This file exceeds the 25 MB limit. Choose a smaller file.",
    empty: "This file is empty. Choose another file.",
    none: null,
  }[fileProblem(file, extensions) ?? "none"];
}

/** The file's SHA-256 (hex): two picks of the same file are refused (review M7). */
export async function sha256(file: File): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

/** Two picks of one file (review M7, D2): the same bytes, whatever the names. */
export async function sameFile(a: File, b: File): Promise<boolean> {
  return a.size === b.size && await sha256(a) === await sha256(b);
}

/** Whether a Word file's text carries tracked changes — read from its own document part
 *  with the browser's zip inflater (no dependency). A warning only: the server reads it. */
export async function hasTrackedChanges(file: File): Promise<boolean> {
  try {
    const zip = new DataView(await file.arrayBuffer());
    let end = zip.byteLength - 22;
    while (end >= 0 && zip.getUint32(end, true) !== 0x06054b50) end -= 1;
    let at = zip.getUint32(end + 16, true);
    for (let n = zip.getUint16(end + 10, true); n > 0; n -= 1) {
      const nameLength = zip.getUint16(at + 28, true);
      const name = new TextDecoder().decode(new Uint8Array(zip.buffer, at + 46, nameLength));
      if (name === "word/document.xml") {
        const local = zip.getUint32(at + 42, true);
        const start = local + 30 + zip.getUint16(local + 26, true) + zip.getUint16(local + 28, true);
        const packed = new Uint8Array(zip.buffer, start, zip.getUint32(at + 20, true));
        const xml = zip.getUint16(at + 10, true) === 0 ? new Blob([packed])
          : new Blob([packed]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
        return /<w:(ins|del|moveFrom|moveTo)\b/.test(await new Response(xml).text());
      }
      at += 46 + nameLength + zip.getUint16(at + 30, true) + zip.getUint16(at + 32, true);
    }
  } catch {
    /* not a readable Word file: the server says what it is */
  }
  return false;
}

export type StartStep = "suggesting" | "analyzing";

/**
 * A new contract from its first file: created (with its client in the same call), the file
 * uploaded with whose paper it is (`AM-324` r4), the type suggested from it and recorded
 * when confident (AM-50), and analysed. Throws only when the contract or the file is
 * refused — `uploadFirstDocument` then archives the empty contract.
 */
export async function startContract(file: File, role: UploadRole, o: {
  name?: string; counterpartyId?: string; compareWith?: CompareWith; canReview: boolean;
  /** the name from the type once it is known (round 2, UI 4); else ``name`` / the file's */
  nameFor?: (type: string | null) => string;
  onCreated?: (contractId: string) => void; onStep?: (step: StartStep, type: string | null) => void;
}): Promise<{ contractId: string; versionId: string; type: string | null }> {
  const name = o.nameFor?.(null) || o.name || nameFromFilename(file.name) || file.name;
  const contract = await api.createContract(name, undefined, o.counterpartyId);
  o.onCreated?.(contract.id);
  const uploaded = await uploadFirstDocument(contract.id, file, role, o.compareWith);
  const versionId = uploaded.document_version.id;
  o.onStep?.("suggesting", null);
  let type: string | null = null;
  try {
    const proposed = await api.suggestType(versionId);
    // AM-51: one optional signal, never a gate — recorded only when confident
    if (proposed.confident && proposed.suggested_type) {
      await api.updateContract(contract.id, { name: o.nameFor?.(proposed.suggested_type) ?? name,
                                              contract_type: proposed.suggested_type,
                                              contract_type_source: "ASSIST_SUGGESTION" });
      type = proposed.suggested_type;
    }
  } catch {
    /* not confident or not recorded: the engine reads the document by its content */
  }
  o.onStep?.("analyzing", type);
  await chainAnalysis(contract.id, o.canReview);
  return { contractId: contract.id, versionId, type };
}
