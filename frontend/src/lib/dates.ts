/**
 * The app's two date formats — one place, so every screen says a date the same way.
 *
 *   DATE       "6 Nov 2026"
 *   DATE_TIME  "6 Nov 2026, 2:05 pm"
 *
 * en-IN, the readers' own convention. The helpers turn an absent or unreadable value
 * into "" (the caller decides whether to show anything), never "Invalid Date".
 */

export const DATE = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric" });
export const DATE_TIME = new Intl.DateTimeFormat("en-IN", {
  day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" });

type When = string | number | Date | null | undefined;

function at(when: When): Date | null {
  if (when === null || when === undefined || when === "") return null;
  const d = when instanceof Date ? when : new Date(when);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function formatDate(when: When): string {
  const d = at(when);
  return d ? DATE.format(d) : "";
}

export function formatDateTime(when: When): string {
  const d = at(when);
  return d ? DATE_TIME.format(d) : "";
}
