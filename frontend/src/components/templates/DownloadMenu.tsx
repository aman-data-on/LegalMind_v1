"use client";

/**
 * A template's file download as a menu button (`AM-302`): one trigger, two formats —
 * "Word (.docx)" and "PDF". The pattern the enterprise template libraries use (a ghost
 * icon button with the download glyph on a row; a quiet text link inside a flow), built
 * to the WAI-ARIA APG menu button: Enter, Space or ↓ opens on the first item, ↑ on the
 * last; ↑/↓ move, Home/End jump, Esc closes and returns focus, Tab closes. The PDF comes
 * from the worker, so "Preparing PDF…" stands while it is made; when it cannot be made
 * the Word file is offered in its place. Presentation only — every download is checked
 * and audited server-side (rule 18).
 */

import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";

import { api, describeError, toApiError } from "@/lib/api";
import { fetchPdf, saveBlob } from "@/lib/pdfDownload";
import { IconDownload } from "@/components/workspace/icons";

import "./download.css";

type Format = "docx" | "pdf";
const ITEMS: { format: Format; label: string }[] = [
  { format: "docx", label: "Word (.docx)" },
  { format: "pdf", label: "PDF" },
];
const PREPARING = "Preparing PDF…";
const NOT_MADE = "The PDF couldn’t be made right now.";
const DONE: Record<Format, string> = { docx: "Word file downloaded.", pdf: "PDF downloaded." };

/** The APG menu's arrow keys: the item to focus, or null for any other key. Wraps. */
export function menuMove(key: string, at: number, n: number): number | null {
  if (key === "ArrowDown") return (at + 1 + n) % n;
  if (key === "ArrowUp") return (at - 1 + n) % n;
  if (key === "Home") return 0;
  if (key === "End") return n - 1;
  return null;
}

async function fetchWord(path: string): Promise<void> {
  const response = await api.pdfResponse(path);
  if (!response.ok) throw await toApiError(response, response.headers.get("X-Request-Id") ?? "-");
  const name = /filename\*=UTF-8''([^;]+)/i.exec(response.headers.get("Content-Disposition") ?? "")?.[1];
  saveBlob(await response.blob(), name ? decodeURIComponent(name) : undefined);
}

export function DownloadMenu({ path, label, variant = "icon", text, align = "end", kind }: {
  /** the API path without `?format=` — `/templates/{key}/blank`, `/templates/{id}/review-copy` */
  path: string;
  /** the trigger's accessible name and tooltip ("Download blank template") */
  label: string;
  variant?: "icon" | "link";
  /** the link's visible words (variant "link"); defaults to `label` */
  text?: string;
  align?: "start" | "end";
  /** names the file in each item ("Review copy, Word (.docx)") where one glyph could mean two files */
  kind?: string;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<Format | null>(null);
  const [waiting, setWaiting] = useState(false);
  const [problem, setProblem] = useState<{ message: string; offerWord: boolean } | null>(null);
  const [done, setDone] = useState("");
  // WCAG 1.4.13: Esc dismisses the tooltip without moving focus; it returns on the next hover
  const [tipGone, setTipGone] = useState(false);
  const trigger = useRef<HTMLButtonElement | null>(null);
  const list = useRef<HTMLDivElement | null>(null);
  const items = useRef<(HTMLButtonElement | null)[]>([]);
  const menuId = useId();
  const join = path.includes("?") ? "&" : "?";

  // APG: opening puts focus on the first (or, from ↑, the last) item once it is drawn
  const [landing, setLanding] = useState(0);
  function show(first: "first" | "last") {
    setLanding(first === "first" ? 0 : ITEMS.length - 1);
    setOpen(true);
  }
  function hide(restore: boolean) {
    setOpen(false);
    if (restore) trigger.current?.focus();
  }
  useEffect(() => { if (open) items.current[landing]?.focus(); }, [open, landing]);

  useEffect(() => {
    if (!open) return;
    function away(event: PointerEvent) {
      const at = event.target as Node;
      if (!list.current?.contains(at) && !trigger.current?.contains(at)) setOpen(false);
    }
    // a menu that would drift from its trigger closes instead (scroll, resize, window blur)
    const shut = () => setOpen(false);
    document.addEventListener("pointerdown", away);
    window.addEventListener("scroll", shut, true);
    window.addEventListener("resize", shut);
    window.addEventListener("blur", shut);
    return () => {
      document.removeEventListener("pointerdown", away);
      window.removeEventListener("scroll", shut, true);
      window.removeEventListener("resize", shut);
      window.removeEventListener("blur", shut);
    };
  }, [open]);

  function onTriggerKey(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
      event.preventDefault(); show("first");
    } else if (event.key === "ArrowUp") {
      event.preventDefault(); show("last");
    } else if (event.key === "Escape") {
      setTipGone(true);
    }
  }
  function onMenuKey(event: KeyboardEvent<HTMLDivElement>) {
    const at = items.current.findIndex((el) => el === document.activeElement);
    const to = menuMove(event.key, at, ITEMS.length);
    if (to !== null) { event.preventDefault(); items.current[to]?.focus(); }
    else if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); hide(true); }
    else if (event.key === "Tab") setOpen(false);
  }

  async function download(format: Format) {
    hide(true);
    setBusy(format); setWaiting(false); setProblem(null); setDone("");
    const url = `${path}${join}format=${format}`;
    try {
      if (format === "docx") {
        await fetchWord(url);
        setDone(DONE.docx);
      } else {
        const got = await fetchPdf(url, { onWaiting: () => setWaiting(true) });
        if (got.kind === "file") { saveBlob(got.blob, got.name); setDone(DONE.pdf); }
        else setProblem({ message: got.kind === "not-made" ? NOT_MADE : got.message, offerWord: true });
      }
    } catch (cause) {
      setProblem({ message: describeError(cause), offerWord: format === "pdf" });
    } finally {
      setBusy(null); setWaiting(false);
    }
  }

  const said = waiting ? PREPARING : busy ? "Downloading…" : done;
  return (
    <div className={`tpl-dl tpl-dl--${variant} tpl-dl--${align}`}>
      <button ref={trigger} type="button"
              className={variant === "icon" ? "tpl-dl__icon" : "tpl-dl__link"}
              aria-haspopup="menu" aria-expanded={open} aria-controls={open ? menuId : undefined}
              aria-label={variant === "icon" ? label : undefined}
              aria-busy={busy ? true : undefined} data-tip-gone={tipGone || undefined}
              onMouseEnter={() => setTipGone(false)} onBlur={() => setTipGone(false)}
              onClick={() => (open ? hide(false) : show("first"))} onKeyDown={onTriggerKey}>
        <IconDownload size={16} />
        {variant === "link" ? <span>{text ?? label}</span> : null}
        {variant === "icon" ? <span className="tpl-dl__tip" aria-hidden="true">{label}</span> : null}
      </button>
      {open ? (
        <div ref={list} id={menuId} className="tpl-dl__menu" role="menu"
             aria-label={label} onKeyDown={onMenuKey}>
          {ITEMS.map((item, i) => (
            <button key={item.format} ref={(el) => { items.current[i] = el; }} type="button"
                    role="menuitem" tabIndex={-1} className="tpl-dl__item"
                    onClick={() => void download(item.format)}>
              {kind ? `${kind}, ${item.label}` : item.label}
            </button>
          ))}
        </div>
      ) : null}
      <span className="tpl-dl__said" role="status" aria-live="polite">{said}</span>
      {problem ? (
        <p className="tpl-dl__problem" role="alert">
          {problem.message}{" "}
          {problem.offerWord ? (
            <button type="button" className="tpl-dl__retry" onClick={() => void download("docx")}>
              Download Word instead
            </button>
          ) : null}
        </p>
      ) : null}
    </div>
  );
}
