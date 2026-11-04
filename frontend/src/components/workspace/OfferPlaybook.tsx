"use client";

/**
 * What we can offer (`AM-305`) — the negotiation playbook, in the deal owner's words.
 * Each line is the server's, derived from our paper and the ratified standard; the
 * screen only orders the points (room to agree first, fixed figures next, Legal-only
 * folded) and sets the sentence "You can agree …" in bold. Read-only: it records
 * nothing and decides nothing, and it is absent for a reader without
 * `legal_position.view` (LEGAL-02 — omitted, never blanked).
 */

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { ClientChange } from "@/lib/changes";
import * as P from "@/lib/permissions";
import { grouped, offerFor, OFFER_WORDS, type PlaybookPoint } from "@/lib/playbook";
import { useSession } from "@/lib/session";
import { within } from "@/lib/templates";

import { requirementTitle } from "./findingLanguage";
import { IconCheckCircle, IconFallback, IconScale } from "./icons";

import "./offer.css";

/** One fetch per contract or template per page: the Summary, the Changes index and the
 *  answer card all read the same promise. */
const loads = new Map<string, Promise<PlaybookPoint[] | "failed">>();

/** The one read per key. It always finishes: the points, or "failed" on an error or past
 *  `within`'s limit — and a failed read is forgotten, so the next attempt asks again. */
export function loadPlaybook(kind: "contract" | "template", id: string): Promise<PlaybookPoint[] | "failed"> {
  const key = `${kind}:${id}`;
  if (!loads.has(key)) {
    const call = kind === "contract" ? api.contractPlaybook(id) : api.templatePlaybook(id);
    loads.set(key, within(call).then((r) => r.points)
      .catch(() => { loads.delete(key); return "failed" as const; }));
  }
  return loads.get(key)!;
}

/** The points; "loading"; "failed" (an error, or past `within`'s limit — the read always
 *  finishes, and a new ``attempt`` asks again); null without the permission. */
export function usePlaybook(kind: "contract" | "template", id: string | null,
                            attempt = 0): PlaybookPoint[] | null | "loading" | "failed" {
  const { can } = useSession();
  const allowed = can(P.LEGAL_POSITION_VIEW);
  // the answer with the read it answers: a new attempt reads "loading" until its own lands
  const want = `${kind}:${id}:${attempt}`;
  const [got, setGot] = useState<{ want: string; points: PlaybookPoint[] | "failed" } | null>(null);
  useEffect(() => {
    if (!allowed || !id) return;
    let live = true;
    void loadPlaybook(kind, id).then((points) => { if (live) setGot({ want, points }); });
    return () => { live = false; };
  }, [kind, id, allowed, want]);
  return allowed && id ? (got?.want === want ? got.points : "loading") : null;
}

const title = (p: PlaybookPoint) => requirementTitle({ code: p.requirement_code });

/** The server's line as sentences, the one that says how far the deal owner may go in bold. */
function Line({ line }: { line: string }) {
  return (
    <p className="lm-offer__line">
      {line.split(/(?<=\.)\s+/).map((s, i) => (
        <span key={i} data-room={/^You can agree/.test(s) || undefined}>{i ? " " : ""}{s}</span>
      ))}
    </p>
  );
}

export function OfferList({ points, id }: { points: PlaybookPoint[]; id?: string }) {
  const { room, fixed, legal } = grouped(points);
  const rest = fixed.length + legal.length;
  const item = (p: PlaybookPoint) => (
    <li key={p.requirement_code} id={id ? `${id}-${p.requirement_code}` : undefined}
        className="lm-offer__point" data-room={p.room || undefined}>
      <span className="lm-offer__title">{title(p)}</span>
      <Line line={p.line} />
    </li>
  );
  return (
    <div className="lm-offer">
      {room.length ? <ul className="lm-offer__list">{room.map(item)}</ul>
        : <p className="lm-offer__intro">No point on this paper leaves room to agree without Legal.</p>}
      {rest ? (
        <details className="lm-offer__legal">
          <summary>Any change goes to Legal on {rest} other {rest === 1 ? "point" : "points"}</summary>
          {fixed.length ? <ul className="lm-offer__list lm-offer__list--fixed">{fixed.map(item)}</ul> : null}
          {legal.length ? <p>{fixed.length ? "Also: " : ""}{legal.map(title).join(", ")}.</p> : null}
        </details>
      ) : null}
    </div>
  );
}

/** The Summary's section: absent while loading, on failure and without the permission. */
export function OfferSection({ contractId }: { contractId: string }) {
  const points = usePlaybook("contract", contractId);
  if (!Array.isArray(points) || !points.length) return null;
  return (
    <section className="ws-summary__part" aria-labelledby="ws-sum-offer">
      <h3 id="ws-sum-offer" className="ws-summary__title">What we can offer</h3>
      <p className="lm-offer__intro">How far you can go without Legal, from our approved positions.</p>
      <OfferList points={points} id="offer" />
    </section>
  );
}

/** A client change against the playbook — on the answer card: the phrase and the line. */
export function OfferLine({ change, contractId }: { change: ClientChange; contractId: string }) {
  const points = usePlaybook("contract", contractId);
  const hit = offerFor(change, Array.isArray(points) ? points : null);
  if (!hit) return null;
  const Icon = hit.fallback ? IconFallback : hit.within ? IconCheckCircle : IconScale;
  return (
    <div className="lm-offer-hit" data-within={(hit.within && !hit.fallback) || undefined}
         data-fallback={hit.fallback || undefined}>
      <p className="lm-offer-hit__said"><Icon size={15} />{hit.fallback ? OFFER_WORDS.fallback : hit.within ? OFFER_WORDS.within : OFFER_WORDS.beyond}</p>
      <p className="lm-offer-hit__point"><span>{title(hit.point)}:</span> {hit.point.line}</p>
    </div>
  );
}

/** The same, as a two-word tag on the Changes index row. */
export function OfferTag({ change, contractId }: { change: ClientChange; contractId: string }) {
  const points = usePlaybook("contract", contractId);
  const hit = offerFor(change, Array.isArray(points) ? points : null);
  if (!hit) return null;
  return <span className="lm-offer-tag" data-within={(hit.within && !hit.fallback) || undefined}>
    {hit.fallback ? "Our fallback" : hit.within ? "Within our offer" : "Beyond our offer"}</span>;
}
