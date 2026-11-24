import { describe, expect, it } from "vitest";

import { briefReads, briefSettled, briefShouldRead } from "@/components/workspace/DealBrief";

/** Plays a page's effect runs through the brief's read policy (P2 BE-5, W1-4). */
describe("the brief is read once per view (W1-4)", () => {
  it("the change list landing after the brief answered does not read again", () => {
    const m = briefReads(null, 0);
    expect(briefShouldRead(m, "c1", null, 0)).toBe(true);    // first load, list still out
    expect(briefSettled(m, "c1")).toBe(false);
    m.shown = "c1";
    expect(briefShouldRead(m, "c1", "{}OPEN,,", 0)).toBe(false);   // /changes landed
  });

  it("the change list landing while the brief is out does not read again", () => {
    const m = briefReads(null, 0);
    expect(briefShouldRead(m, "c1", null, 0)).toBe(true);
    expect(briefShouldRead(m, "c1", "{}OPEN,,", 0)).toBe(false);
    expect(briefSettled(m, "c1")).toBe(false);
  });

  it("a real change afterwards reads again: an answer saved (ties) or a reload", () => {
    const m = briefReads(null, 0);
    briefShouldRead(m, "c1", null, 0);
    briefSettled(m, "c1");
    m.shown = "c1";
    briefShouldRead(m, "c1", "{}OPEN,,", 0);
    expect(briefShouldRead(m, "c1", "{}OPEN,AS_TOLD,", 0)).toBe(true);   // a tie recorded
    expect(briefShouldRead(m, "c1", "{}OPEN,AS_TOLD,", 1)).toBe(true);   // reload()
  });

  it("a page with no change list (key known from the start) reads once, then on changes", () => {
    const m = briefReads("{}OPEN", 0);
    expect(briefShouldRead(m, "c1", "{}OPEN", 0)).toBe(true);
    briefSettled(m, "c1");
    m.shown = "c1";
    expect(briefShouldRead(m, "c1", "{\"points_open\":1}OPEN", 0)).toBe(true);
  });

  it("another contract always reads", () => {
    const m = briefReads(null, 0);
    briefShouldRead(m, "c1", null, 0);
    briefSettled(m, "c1");
    m.shown = "c1";
    expect(briefShouldRead(m, "c2", null, 0)).toBe(true);
  });

  it("two real changes while the first read is out read again when it lands", () => {
    const m = briefReads(null, 0);
    briefShouldRead(m, "c1", null, 0);
    briefShouldRead(m, "c1", "a", 0);
    briefShouldRead(m, "c1", "b", 0);
    expect(briefSettled(m, "c1")).toBe(true);
  });
});
