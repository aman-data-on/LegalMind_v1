/**
 * Cross-page consistency (`AM-291`): two nouns from one server `counts` object, one
 * label per action, one primary step per person per stage, one status set, one time.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { PageHeader } from "@/components/page/PageHeader";
import { POINT_STATUS, PointStatusLegend } from "@/components/workspace/PointStatus";
import { StageBadge } from "@/components/workspace/StageBadge";
import { relativeTime } from "@/components/workspace/model";
import { ACTION, changesWords, pointsWords, stageLine } from "@/lib/labels";
import { nextStep, taskAction } from "@/lib/nextStep";

const round = { changes_total: 82, changes_left: 81, changes_left_for_me: 19, points_open: 15, points_for_me: 0 };

describe("the two nouns", () => {
  it("says changes as yours of the total, and who has the rest", () => {
    expect(changesWords(round)).toBe("19 of 82 changes yours");
    expect(changesWords({ ...round, changes_left_for_me: 0 })).toBe("81 of 82 changes with Legal");
    expect(changesWords({ ...round, changes_left_for_me: 0 }, "legal")).toBe("81 of 82 changes with the deal owner");
    expect(changesWords({ ...round, changes_left: 0, changes_left_for_me: 0 })).toBe("All 82 changes answered");
    expect(changesWords({ points_open: 3 })).toBeNull();           // no round: absent, not 0
  });
  it("says points as open, or to decide for the holder", () => {
    expect(pointsWords(round)).toBe("15 open points");
    expect(pointsWords({ points_open: 15, points_for_me: 15 }, "legal")).toBe("15 points to decide");
    expect(pointsWords({ points_open: 0 })).toBe("No open points");
    expect(pointsWords({})).toBeNull();
  });
});

describe("the stage line agrees with the counts", () => {
  const answered = { changes_total: 82, changes_left: 0, changes_left_for_me: 0, points_open: 17 };
  it("names the real next step once every change is answered", () => {
    expect(stageLine("INTERNAL_REVIEW", answered, "owner")).toBe("With Legal, 17 points");
    expect(stageLine("INTERNAL_REVIEW", answered, "legal")).toBe("Legal deciding 17 points");
    expect(stageLine("CLIENT_RETURNED", answered)).toBe("Changes answered, reply next");
    expect(stageLine("CLIENT_RETURNED", round)).toBe("Client replied");
    expect(stageLine("INTERNAL_REVIEW", { points_open: 0 }, "legal")).toBe("Your review");
  });
  it("draws the same words on the chip", () => {
    const html = renderToStaticMarkup(
      <StageBadge stage={{ stage: "INTERNAL_REVIEW", since: new Date().toISOString(), days: 0 }}
                  counts={answered} />);
    expect(html).toContain("With Legal, 17 points");
    expect(html).toContain("just now");
  });
});

describe("one primary step per person per stage", () => {
  const owner = { viewer: "owner" as const, canAnswer: true };
  it("gives each person one named act", () => {
    expect(nextStep({ ...owner, stage: "CLIENT_RETURNED", counts: round })?.label).toBe("Answer changes");
    expect(nextStep({ ...owner, stage: "CLIENT_RETURNED",
      counts: { ...round, changes_left: 0, changes_left_for_me: 0 } })?.label).toBe("Prepare our reply");
    expect(nextStep({ ...owner, stage: "CLIENT_RETURNED",
      counts: { ...round, changes_left_for_me: 0 } })).toBeNull();     // what is left is Legal's
    expect(nextStep({ ...owner, stage: "READY_TO_SEND", replyReady: true })?.label).toBe("Send our reply");
    expect(nextStep({ ...owner, stage: "READY_TO_SEND", draftUnsent: true })?.label)   // Legal decided our draft
      .toBe("Send to client");
    expect(nextStep({ ...owner, stage: "DRAFTING", counts: { points_open: 8 }, canSendToLegal: true })?.label)
      .toBe("Send to Legal");
    expect(nextStep({ ...owner, stage: "INTERNAL_REVIEW", counts: { points_open: 17 }, canSendToLegal: true })?.label)
      .toBe("Send to Legal");
    expect(nextStep({ ...owner, stage: "INTERNAL_REVIEW", counts: { points_open: 17 } })).toBeNull();  // Legal has it
    expect(nextStep({ ...owner, stage: "DRAFTING", counts: { points_open: 0 }, draftUnsent: true })?.label)
      .toBe("Send to client");
    expect(nextStep({ viewer: "legal", canAnswer: false, stage: "INTERNAL_REVIEW",
      counts: { points_open: 17, points_for_me: 17 } })?.label).toBe("Decide 17 points");
    expect(nextStep({ ...owner, canAnswer: false, stage: "CLIENT_RETURNED", counts: round })).toBeNull();
  });
  it("labels a task with the header's own words", () => {
    expect(taskAction({ kind: "decide", count: 17 })).toBe(nextStep({ viewer: "legal", canAnswer: false,
      counts: { points_for_me: 17 } })?.label);
    expect(taskAction({ kind: "changes_to_answer" })).toBe(ACTION.answerChanges);
    expect(taskAction({ kind: "reply_ready" })).toBe(ACTION.sendReply);
    expect(taskAction({ kind: "client_returned", counts: { changes_total: 4, changes_left: 0 } }))
      .toBe(ACTION.prepareReply);
  });
});

describe("one status set", () => {
  it("lists the four marks in one order, each with its own icon", () => {
    const html = renderToStaticMarkup(<PointStatusLegend />);
    const words = Object.values(POINT_STATUS);
    expect(words).toEqual(["Matches our standard", "Open point", "Decided", "Missing"]);
    for (const w of words) expect(html).toContain(w);
    expect(new Set(html.match(/lucide-[a-z-]+/g)).size).toBeGreaterThanOrEqual(4);
  });
});

describe("one relative time", () => {
  afterEach(() => vi.useRealTimers());
  it("spells the age out", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-11-03T12:00:00Z"));
    const ago = (s: number) => relativeTime(new Date(Date.now() - s * 1000).toISOString());
    expect([ago(30), ago(60 * 12), ago(3600), ago(4 * 3600), ago(30 * 3600), ago(3 * 86400)])
      .toEqual(["just now", "12 minutes ago", "1 hour ago", "4 hours ago", "yesterday", "3 days ago"]);
    expect(ago(40 * 86400)).toBe("24 Sept 2026");
  });
});

describe("PageHeader", () => {
  it("has a text back link, one title and at most the one primary given", () => {
    const html = renderToStaticMarkup(
      <PageHeader title="Client A MSA" back={{ href: "/contracts", label: "Contracts" }}
                  primary={<button className="ws-btn ws-btn--primary">Answer changes</button>} />);
    expect(html).toMatch(/<a[^>]*href="\/contracts"[^>]*>.*Contracts<\/a>/);
    expect((html.match(/<h1/g) ?? []).length).toBe(1);
    expect((html.match(/ws-btn--primary/g) ?? []).length).toBe(1);
  });
});
