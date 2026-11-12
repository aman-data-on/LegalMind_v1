import { describe, expect, it } from "vitest";

import { DATE, DATE_TIME, formatDate, formatDateTime } from "@/lib/dates";

describe("lib/dates — the app's two date formats", () => {
  it("says a date one way, en-IN", () => {
    expect(formatDate("2026-11-06T06:30:00Z")).toBe(DATE.format(new Date("2026-11-06T06:30:00Z")));
    expect(formatDate("2026-11-06T06:30:00Z")).toMatch(/^6 Nov 2026$/);
    expect(formatDateTime("2026-11-06T06:30:00Z")).toBe(DATE_TIME.format(new Date("2026-11-06T06:30:00Z")));
    expect(formatDateTime("2026-11-06T06:30:00Z")).toMatch(/^6 Nov 2026, \d{1,2}:\d\d (am|pm)$/);
  });
  it("leaves an absent or unreadable value empty, never 'Invalid Date'", () => {
    for (const v of [null, undefined, "", "not a date"]) {
      expect(formatDate(v)).toBe("");
      expect(formatDateTime(v)).toBe("");
    }
  });
});
