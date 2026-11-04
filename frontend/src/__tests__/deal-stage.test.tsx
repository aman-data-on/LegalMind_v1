/**
 * CLM R7 (`AM-260`/`AM-261`): the deal stage is its own badge in its own words — never a
 * legal-state pill — and "Client returned" is marked as our turn without colour alone.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { STAGE_LABEL, STAGE_ORDER, StageBadge } from "@/components/workspace/StageBadge";

describe("StageBadge", () => {
  it("names all eight stages in the deal's order", () => {
    expect(STAGE_ORDER.map((s) => STAGE_LABEL[s])).toEqual([
      "Drafting", "With Legal", "With client", "Client replied",
      "Ready to send", "Ready to sign", "Signed", "On hold"]);
  });

  it("shows the stage and its days, and says our turn in words", () => {
    const html = renderToStaticMarkup(
      <StageBadge stage={{ stage: "CLIENT_RETURNED",
        since: new Date(Date.now() - 9.2 * 86400e3).toISOString(), days: 9 }} />);
    expect(html).toContain("Client replied");
    expect(html).toContain("9 days ago");          // the one relative-time format
    expect(html).toContain(", our turn");
    expect(html).toContain("ws-dealstage--turn");
    expect(html).not.toMatch(/ws-state|ws-axis|StatePill/);
  });

  it("says a stage reached just now in words, never \"0 days\"", () => {
    const html = renderToStaticMarkup(
      <StageBadge stage={{ stage: "WITH_CLIENT", since: new Date().toISOString(), days: 0 }} />);
    expect(html).toContain("just now");
    expect(html).not.toContain("0 days");
  });

  it("is an honest dash when the server sent no stage", () => {
    expect(renderToStaticMarkup(<StageBadge stage={undefined} />)).toContain("—");
  });

  it("words the same stage for whoever reads it (S1): the owner's With Legal is the lawyer's review", () => {
    const stage = { stage: "INTERNAL_REVIEW" as const, since: "2026-11-02T00:00:00Z", days: 1 };
    expect(renderToStaticMarkup(<StageBadge stage={stage} />)).toContain("With Legal");
    expect(renderToStaticMarkup(<StageBadge stage={stage} viewer="legal" />)).toContain("Your review");
    // only Internal review differs by reader
    expect(renderToStaticMarkup(<StageBadge stage={{ ...stage, stage: "CLIENT_RETURNED" }} viewer="legal" />))
      .toContain("Client replied");
  });
});
