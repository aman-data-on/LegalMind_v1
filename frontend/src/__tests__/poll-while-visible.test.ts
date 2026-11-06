import { afterEach, describe, expect, it, vi } from "vitest";

import { pollWhileVisible } from "@/lib/utils";

// node environment: a minimal document (an EventTarget with `hidden`)
const doc = Object.assign(new EventTarget(), { hidden: false });
const setHidden = (hidden: boolean) => {
  doc.hidden = hidden;
  doc.dispatchEvent(new Event("visibilitychange"));
};

describe("pollWhileVisible", () => {
  afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

  it("skips ticks while hidden, refreshes once when shown, and stops", () => {
    vi.useFakeTimers();
    vi.stubGlobal("document", doc);
    const run = vi.fn();
    const stop = pollWhileVisible(run, 1000);
    vi.advanceTimersByTime(1000);
    expect(run).toHaveBeenCalledTimes(1);
    setHidden(true);
    vi.advanceTimersByTime(5000);
    expect(run).toHaveBeenCalledTimes(1);
    setHidden(false);
    expect(run).toHaveBeenCalledTimes(2);
    stop();
    vi.advanceTimersByTime(5000);
    setHidden(false);
    expect(run).toHaveBeenCalledTimes(2);
  });
});
