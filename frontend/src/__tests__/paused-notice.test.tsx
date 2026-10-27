/** AM-222 (2026-10-27): when the AI provider stops serving us (credit or quota), the
 *  reader is told before typing — in plain words, never the billing cause — and only a
 *  platform administrator sees why. */
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { PausedNotice } from "@/components/workspace/ModelPicker";
import type { AskModel } from "@/lib/types";

const gemini: AskModel = { id: "gemini", label: "Gemini", default: true, configured: true };

describe("PausedNotice", () => {
  it("says nothing while the model is serving", () => {
    expect(renderToStaticMarkup(<PausedNotice model={null} />)).toBe("");
  });

  it("tells a reader plainly, with what still works and no billing words", () => {
    const html = renderToStaticMarkup(<PausedNotice model={{ ...gemini, paused: true }} />);
    expect(html).not.toContain("For admins");
    expect(html).toContain('role="status"');
    expect(html).toContain("AI answers are paused");
    expect(html).toContain("Your chats, contracts and reviews are all still here");
    expect(html).not.toMatch(/credit|billing|payment|quota|402/i);
  });

  it("names the cause to an administrator, whom the server alone tells", () => {
    const html = renderToStaticMarkup(<PausedNotice model={{
      ...gemini, paused: true,
      paused_reason: { kind: "payment", since: "2026-10-27T08:00:00+00:00" } }} />);
    expect(html).toContain("For admins: Gemini’s credit ran out at");
    expect(html).toContain("Answers resume on their own");
  });
});
