"use client";

import { formatDate } from "@/lib/dates";
import { REPLY_NOTICE_COPY as COPY } from "@/lib/labels";
import type { DocumentVersion } from "@/lib/types";

import { ReplyDownloads } from "./changesFeed";

/** The Document tab says what a reply version IS (`AM-251`): ours, answering the
 *  client's, with its files — and, once sent, when. U2 r4: one short line that always
 *  shows, on a phone too — what to restore by hand, then the next act or when it went. */
export function ReplyNotice({ version, versions, canSend }: {
  version: DocumentVersion; versions: DocumentVersion[]; canSend: boolean;
}) {
  const reply = version.reply;
  if (!reply) return null;
  const theirs = versions.find((v) => v.id === reply.to_version_id);
  const byHand = reply.by_hand ?? [];
  return (
    <section className="ws-replynote" aria-label={COPY.label} data-sent={version.sent_at ? "" : undefined}>
      <div className="ws-replynote__text">
        <p className="ws-replynote__title">{COPY.title(version.version_number, theirs?.version_number)}</p>
        <p className="ws-replynote__sub">
          {byHand.length ? `${COPY.byHand(byHand)} ` : ""}
          {version.sent_at ? <strong>{COPY.sentOn(formatDate(version.sent_at))}</strong>
            : canSend ? COPY.next : COPY.notSent}
        </p>
      </div>
      <div className="ws-replynote__acts">
        <ReplyDownloads version={version} />
      </div>
    </section>
  );
}
