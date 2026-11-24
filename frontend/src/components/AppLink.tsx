"use client";

import NextLink, { useLinkStatus } from "next/link";
import { useEffect, useRef, useState, type ComponentProps } from "react";

/** A record's address (an id in the path): a dynamic route, which Next prefetches only down
 *  to the nearest `loading.js` — there is none, so intent would fetch nothing useful. */
const RECORD = /\/[0-9a-f]{8}-[0-9a-f]{4}-/;

/** W1-1 r2 (M3): the tap answered at once — while the route loads, the link carries
 *  `data-pending` (styled by opacity, so nothing moves). Renders nothing: it only reads
 *  `useLinkStatus`, which must sit inside the link. */
function Pending({ link }: { link: React.RefObject<HTMLAnchorElement | null> }) {
  const { pending } = useLinkStatus();
  useEffect(() => { link.current?.toggleAttribute("data-pending", pending); }, [link, pending]);
  return null;
}

/**
 * W1-1 (RC-3): the app's one link. Next prefetches every `<Link>` that scrolls into view; on
 * a phone that doubled each page's JS bytes and queued ahead of the page's own requests. Here
 * a route is prefetched only on intent — a pointer over it, focus, or a finger down — the
 * Next docs' "Hover-triggered prefetch" (`prefetch={null}` once shown intent, never before).
 * `next/link` is imported only here (eslint `no-restricted-imports`, `app-link.test.ts`).
 */
export default function Link({ onMouseEnter, onFocus, onTouchStart, children, ...props }: ComponentProps<typeof NextLink>) {
  const [intent, setIntent] = useState(false);
  const link = useRef<HTMLAnchorElement>(null);
  const record = typeof props.href === "string" && RECORD.test(props.href);
  const want = () => { if (!record) setIntent(true); };
  return (
    <NextLink {...props} ref={link} prefetch={intent ? null : false}
              onMouseEnter={(event) => { want(); onMouseEnter?.(event); }}
              onFocus={(event) => { want(); onFocus?.(event); }}
              onTouchStart={(event) => { want(); onTouchStart?.(event); }}>
      {children}<Pending link={link} />
    </NextLink>
  );
}
