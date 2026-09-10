"use client";

/**
 * The small shared pieces of Client Profiles: the avatar block, the status
 * reading, and the "field or Not available" pair.
 *
 * They live together because each one encodes a rule that must hold on every
 * surface at once, and a rule copied into three callers is a rule that gets
 * fixed in one of them (the `sectionRef` lesson in `documentTypes.ts`).
 */

import { clientStatusLabel, companyInitials } from "@/lib/documentTypes";

/**
 * A company's initials block.
 *
 * `aria-hidden`, always: it carries no information the full name beside it does
 * not, and announcing "A T" before every company name would make the list
 * slower to hear than to read.
 */
export function ClientAvatar({ name, size = "md" }: {
  name: string;
  size?: "sm" | "md" | "lg";
}) {
  return (
    <span className={`ws-cl__avatar ws-cl__avatar--${size}`} aria-hidden="true">
      {companyInitials(name)}
    </span>
  );
}

/**
 * A client's relationship status — a dot plus the word, always both.
 *
 * ⚠️ **Deliberately neutral, not the traffic light.** DESIGN.md reserves colour
 * for the five legal state axes plus attention and error, and the app already
 * spends green on "Acceptable" and amber on "Requires modification". Painting a
 * client ACTIVE in that same green would put a filing state into a legal
 * channel — within a week a reader would take a green client as a reviewed one.
 *
 * So the dot varies by FILL and WEIGHT rather than hue, the word is always
 * present (accessibility floor: never colour alone), and the colour budget on
 * this screen is spent where it belongs — on the document rows, which are the
 * things that actually need attention.
 */
export function ClientStatus({ status }: { status: string }) {
  const key = status.toLowerCase();
  return (
    <span className={`ws-cl__status ws-cl__status--${key}`}>
      <span className="ws-cl__dot" aria-hidden="true" />
      {clientStatusLabel(status)}
    </span>
  );
}

/**
 * One label/value pair, where an absent value says so in words.
 *
 * "Not available" and never "—": a dash reads as a checked-and-empty field,
 * and rule 21's discipline is that we do not know this rather than that it is
 * blank. The server omits the key entirely for exactly this reason, and this
 * is the rendering that keeps the distinction visible to the reader.
 */
export function Fact({ label, value, href }: {
  label: string;
  /** `undefined` is the server's own "nobody said" (a key it omitted); `null`
   *  is a caller that looked and found nothing. Both render "Not available" —
   *  the distinction matters to the API contract, not to the reader. */
  value?: string | null | undefined;
  /** A real link where the value is one (a website, an email). */
  href?: string | null | undefined;
}) {
  return (
    <div className="ws-cl__fact">
      <dt>{label}</dt>
      <dd>
        {value
          ? (href
            ? <a href={href} {...(href.startsWith("http")
                ? { target: "_blank", rel: "noreferrer noopener" } : {})}>{value}</a>
            : value)
          : <span className="ws-cl__absent">Not available</span>}
      </dd>
    </div>
  );
}

/** A website as typed, made clickable without rewriting what the human wrote.
 *  A bare "example.test" gets a scheme so the link works; anything already
 *  carrying one is left exactly as it is. */
export function websiteHref(website: string | undefined): string | null {
  if (!website) return null;
  return /^https?:\/\//i.test(website) ? website : `https://${website}`;
}
