"use client";

/**
 * "File into contract" — `AM-269` r2 (AB-150, R10). A file attached in Ask stays the
 * chat's until the reader presses this and names the contract; it then becomes that
 * contract's next version, marked as the client's returned copy. Ask never does it by
 * itself. The contracts offered come from the server (the reader's own and those they
 * collaborate on); none is offered, nothing is shown.
 *
 * The chat keeps no copy of the file (A-15). When the browser still holds it from this
 * session it is sent again; otherwise the reader chooses it again, and the server
 * checks it is the same file.
 */
import Link from "next/link";
import { useRef, useState } from "react";

import { api, attachedFiles, describeError } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { ChatAttachment } from "@/lib/types";

const FILEABLE = new Set([
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
]);

export function fileable(a: ChatAttachment): boolean {
  return a.kind === "FILE" && a.status === "READY" && FILEABLE.has(a.mime_type);
}

export function FileIntoContract({ conversationId, attachment }: {
  conversationId: string; attachment: ChatAttachment;
}) {
  const [targets, setTargets] = useState<{ id: string; name: string }[] | null>(null);
  const [pick, setPick] = useState("");
  const [state, setState] = useState<"idle" | "busy" | "done">("idle");
  const [error, setError] = useState<string | null>(null);
  const chooser = useRef<HTMLInputElement>(null);
  const { can } = useSession();

  async function send(file: File) {
    setState("busy");
    setError(null);
    try {
      await api.fileAttachment(conversationId, attachment.id, pick, file);
      setState("done");
    } catch (e) {
      setError(describeError(e));
      setState("idle");
    }
  }

  if (!can(P.DOCUMENT_UPLOAD)) return null;      // presentation only; the server decides
  if (state === "done") {
    return (
      <span className="ws-chat__file" role="status">
        Filed as the client&apos;s returned version.{" "}
        <Link href={`/contracts/${pick}/changes`}>Open its changes</Link>
      </span>
    );
  }
  if (targets === null) {
    return (
      <span className="ws-chat__file">
        <button type="button" className="ws-escalate__link" onClick={() => {
          api.fileTargets(conversationId, attachment.id).then((t) => {
            setTargets(t);
            setPick(t[0]?.id ?? "");
          }).catch((e) => setError(describeError(e)));
        }}>
          File into a contract…
        </button>
        {error ? <span role="alert">{error}</span> : null}
      </span>
    );
  }
  if (targets.length === 0) {
    return <span className="ws-chat__file">There is no contract you can file this into.</span>;
  }
  return (
    <span className="ws-chat__file">
      <label className="ws-chat__filelabel" htmlFor={`ws-file-${attachment.id}`}>File into</label>
      <select id={`ws-file-${attachment.id}`} value={pick} onChange={(e) => setPick(e.target.value)}>
        {targets.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
      </select>
      <button type="button" className="ws-btn ws-btn--sm ws-btn--primary"
              disabled={!pick || state === "busy"} onClick={() => {
        const held = attachedFiles.get(attachment.id);
        if (held) void send(held);
        else chooser.current?.click();
      }}>
        {state === "busy" ? "Filing…" : "File as the client's returned version"}
      </button>
      <button type="button" className="ws-escalate__link" onClick={() => setTargets(null)}>Cancel</button>
      <input ref={chooser} type="file" hidden accept=".pdf,.docx"
             aria-label={`Choose ${attachment.filename ?? "the file"} again`}
             onChange={(e) => { const f = e.target.files?.[0]; if (f) void send(f); }} />
      {attachedFiles.has(attachment.id) ? null : (
        <span>You will be asked to choose {attachment.filename ?? "the file"} again.</span>
      )}
      {error ? <span role="alert">{error}</span> : null}
    </span>
  );
}
