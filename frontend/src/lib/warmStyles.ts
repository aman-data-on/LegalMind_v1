/**
 * W2 r3: the sign-in page no longer carries the workspace stylesheet (W2-1), so the first
 * navigation after signing in waited for it (+~400 ms on a phone). Once /login has loaded and
 * the browser is idle, the stylesheets of the page the reader will land on are downloaded and
 * parsed but NOT applied (`media="not all"`), so the navigation finds them ready.
 *
 * The URLs are hashed per build. They are read from that page's own server-rendered HTML (the
 * `<link rel="stylesheet">` and style-preload tags Next renders for its route), never hard-coded. Skipped on
 * Save-Data and 2g connections, and never started before `load`.
 */
import { pageHtml } from "./api";

type Connection = { saveData?: boolean; effectiveType?: string };

export function warmStylesAfterLoad(path: string): () => void {
  const connection = (navigator as Navigator & { connection?: Connection }).connection;
  if (connection?.saveData || /2g/.test(connection?.effectiveType ?? "")) return () => undefined;
  // only a same-origin page route (`next=` is reader-supplied): never the API or another origin
  if (!/^\/(?!\/|\\|api\/)/.test(path)) return () => undefined;
  let cancelled = false;
  const warm = async () => {
    if (cancelled) return;
    try {
      const html = await pageHtml(path);
      if (cancelled) return;
      const doc = new DOMParser().parseFromString(html, "text/html");
      const have = new Set([...document.querySelectorAll<HTMLLinkElement>('link[rel="stylesheet"]')].map((l) => l.href));
      for (const sheet of doc.querySelectorAll<HTMLLinkElement>('link[rel="stylesheet"][href], link[rel="preload"][as="style"][href]')) {
        const href = new URL(sheet.getAttribute("href")!, location.href).href;
        if (have.has(href) || new URL(href).origin !== location.origin) continue;
        const link = document.createElement("link");
        // media "not all": downloaded AND parsed now, applied never — the navigation's own
        // <link rel="stylesheet"> for the same URL reuses Chrome's parsed copy (a prefetch only
        // saved the download; the parse of the 276 KB sheet stayed on the navigation's path)
        link.rel = "stylesheet"; link.media = "not all"; link.href = href;
        document.head.appendChild(link);
      }
      // …and its scripts, downloaded only (never run): the shell's chunks used to arrive with
      // /login when the root 404 pulled them in (W2-1/W2-2 took them off /login's first load)
      const scripts = new Set([...document.scripts].map((x) => x.src));
      for (const el of doc.querySelectorAll<HTMLElement>('script[src], link[rel="preload"][as="script"][href]')) {
        const href = new URL(el.getAttribute("src") ?? el.getAttribute("href")!, location.href).href;
        if (scripts.has(href) || new URL(href).origin !== location.origin) continue;
        scripts.add(href);
        const link = document.createElement("link");
        link.rel = "prefetch"; link.as = "script"; link.href = href;
        document.head.appendChild(link);
      }
    } catch { /* a warm-up only: the navigation loads them anyway */ }
  };
  const idle = () => {
    if ("requestIdleCallback" in window) window.requestIdleCallback(() => void warm(), { timeout: 3000 });
    else setTimeout(() => void warm(), 200);
  };
  if (document.readyState === "complete") idle();
  else window.addEventListener("load", idle, { once: true });
  return () => { cancelled = true; window.removeEventListener("load", idle); };
}
