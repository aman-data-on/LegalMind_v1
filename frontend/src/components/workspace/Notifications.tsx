"use client";

/**
 * The bell's panel — `AM-273` m3 (AB-150, R9). The server writes each notice as a fixed
 * sentence and a link; nothing here composes or adds to it. Unread is a quiet dot and a
 * count said in words, never a red badge (no urgency theatre). The list is re-read when
 * the panel opens and every two minutes, which is enough for a decision request.
 */
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { api, type NotificationList } from "@/lib/api";

import { IconBell } from "./icons";

const POLL_MS = 120_000;

/** `signedIn` gates every read: before the session resolves a 401 would sign the
 *  reader out (QA-027). */
export function useNotifications(open: boolean, signedIn: boolean) {
  const [list, setList] = useState<NotificationList>({ unread: 0, items: [] });
  const reload = useCallback(() => {
    api.notifications().then(setList).catch(() => undefined);
  }, []);
  useEffect(() => {
    if (!signedIn) return;
    reload();
    const timer = window.setInterval(reload, POLL_MS);
    return () => window.clearInterval(timer);
  }, [reload, signedIn]);
  useEffect(() => { if (open && signedIn) reload(); }, [open, signedIn, reload]);
  return { list, reload };
}

export function BellToggle({ unread, open, onClick }: {
  unread: number; open: boolean; onClick: () => void;
}) {
  return (
    <button type="button" className="ws-shell__belltoggle" data-toggle="bell"
            aria-haspopup="dialog" aria-expanded={open}
            aria-label={unread ? `Notifications, ${unread} unread` : "Notifications"}
            onClick={onClick}>
      <IconBell size={17} />
      {unread ? <span className="ws-shell__belldot" aria-hidden="true" /> : null}
    </button>
  );
}

export function NotificationPanel({ list, reload, onClose }: {
  list: NotificationList; reload: () => void; onClose: () => void;
}) {
  return (
    <div className="ws-menu__list ws-shell__menu ws-shell__notes" role="dialog"
         aria-label="Notifications" data-pop="bell">
      <div className="ws-notes__head">
        <strong tabIndex={-1}>Notifications</strong>
        {list.unread ? (
          <button type="button" className="ws-escalate__link"
                  onClick={() => { void api.readAllNotifications().then(reload); }}>
            Mark all as read
          </button>
        ) : null}
      </div>
      {list.items.length === 0 ? (
        <p className="ws-notes__empty">
          <strong>No notifications</strong>
          <span>You are told here when someone asks you to decide a point, when a point
            is decided, and when a client returns a new version.</span>
        </p>
      ) : (
        <ul className="ws-notes__list">
          {list.items.map((n) => (
            <li key={n.id} data-unread={n.read_at ? undefined : ""}>
              <Link href={n.link} onClick={() => {
                if (!n.read_at) void api.readNotification(n.id).then(reload);
                onClose();
              }}>
                <span>{n.sentence}</span>
                <time dateTime={n.created_at}>
                  {new Date(n.created_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}
                </time>
              </Link>
              {n.read_at ? null : <span className="ws-visually-hidden">Unread</span>}
            </li>
          ))}
        </ul>
      )}
      <div className="ws-notes__foot">
        <Link href="/todo" onClick={onClose}>Open your to-do</Link>
      </div>
    </div>
  );
}
