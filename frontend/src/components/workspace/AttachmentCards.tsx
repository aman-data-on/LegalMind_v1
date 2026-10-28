"use client";

/**
 * The files about to be sent with a question, as cards (`AM-226`): a type tile, the
 * name, the type and size — or, for a file that cannot be sent, why, in the card
 * itself. Each card has its own remove control. Nothing is uploaded here: files are
 * saved to the chat when the question is sent (`AM-133`).
 */
import { IconAlertCircle, IconX } from "./icons";

export interface PendingFile {
  key: string;
  file: File;
  /** Why it cannot be sent; such a card is never uploaded. */
  problem: string | null;
}

/** The server's refusal of one file, in the card's words — never the raw code. */
const REFUSED: Record<string, string> = {
  EMPTY_FILE: "the file is empty",
  FILE_TOO_LARGE: "larger than 10 MB",
  PASTE_TOO_LONG: "the text is too long",
  TOO_MANY_ATTACHMENTS: "a chat holds up to 10 files",
  UNSUPPORTED_TYPE: "use PDF, Word, Markdown or text",
  CONTENT_TYPE_MISMATCH: "its content does not match its file type",
  UNRECOGNISED_CONTENT: "its content is not a readable PDF, Word or text file",
};

/** A refusal of the file itself (`the attachment was refused: CODE`), or null for any
 *  other failure — the network, a timeout, Stop — which the message log still reports. */
export function refusalText(cause: unknown): string | null {
  const code = cause instanceof Error ? /attachment was refused: ([A-Z_]+)/.exec(cause.message)?.[1] : undefined;
  return code ? REFUSED[code] ?? "the server could not take this file" : null;
}

const KINDS: Record<string, string> = { pdf: "PDF", docx: "Word", md: "Markdown", txt: "Text" };

function extension(name: string): string {
  return name.includes(".") ? name.slice(name.lastIndexOf(".") + 1).toLowerCase() : "";
}

export function fileSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function AttachmentCards({ files, onRemove, disabled = false }: {
  files: PendingFile[];
  onRemove: (key: string) => void;
  /** While the question is sent: a removed card would still be uploaded. */
  disabled?: boolean;
}) {
  if (files.length === 0) return null;
  return (
    <ul className="ws-chat__cards" aria-label="Files to send">
      {files.map(({ key, file, problem }) => {
        const ext = extension(file.name);
        return (
          <li key={key} className="ws-chat__card" data-problem={problem ? "" : undefined}>
            <span className="ws-chat__cardtile" aria-hidden="true">
              {problem ? <IconAlertCircle size={18} /> : (ext || "file").toUpperCase()}
            </span>
            <span className="ws-chat__cardtext">
              <span className="ws-chat__cardname" title={file.name}>{file.name}</span>
              <span className="ws-chat__cardmeta">
                {problem ? `Not sent: ${problem}` : `${KINDS[ext] ?? "File"}, ${fileSize(file.size)}`}
              </span>
            </span>
            <button type="button" className="ws-chat__cardremove" aria-label={`Remove ${file.name}`}
                    disabled={disabled} onClick={() => onRemove(key)}>
              <IconX size={14} />
            </button>
          </li>
        );
      })}
    </ul>
  );
}
