/**
 * CLM R7 (`AM-260`/`AM-261`): the deal stage is its own badge in its own words — never a
 * legal-state pill — and "Client returned" is marked as our turn without colour alone.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { CountsCell, STAGE_LABEL, STAGE_ORDER, StageBadge } from "@/components/workspace/StageBadge";
import { ClosedPanel } from "@/components/workspace/FinalCopy";
import type { Contract } from "@/lib/types";

describe("StageBadge", () => {
  it("names all nine stages in the deal's order (AM-318: Final ends it)", () => {
    expect(STAGE_ORDER.map((s) => STAGE_LABEL[s])).toEqual([
      "Drafting", "With Legal", "With client", "Client replied",
      "Ready to send", "Ready for the final contract", "Final", "Signed", "On hold"]);
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

describe("CountsCell", () => {
  const counts = { changes_total: 82, changes_left: 3, changes_left_for_me: 3, points_open: 15 };
  const row = (stage: string) => ({ id: "c1", name: "MSA", counts,
    negotiation_stage: { stage, since: "2026-11-02T00:00:00Z", days: 1 } }) as unknown as Contract;

  it("a signed contract's row says only Signed, never its points or changes", () => {
    const html = renderToStaticMarkup(<CountsCell contract={row("SIGNED")} viewer="owner" />);
    expect(html).toContain("Signed");
    expect(html).not.toMatch(/point|change/);
  });

  it("an open deal still shows its counts", () => {
    const html = renderToStaticMarkup(<CountsCell contract={row("WITH_CLIENT")} viewer="owner" />);
    expect(html).toContain("15 open points");
    expect(html).toContain("3 of 82 changes yours");
  });
});

describe("Final (AM-318)", () => {
  const since = "2026-11-09T06:00:00Z";
  it("the chip says Final and the date, the row says the copy is ready", () => {
    const chip = renderToStaticMarkup(<StageBadge stage={{ stage: "FINAL", since, days: 0 }} />);
    expect(chip).toContain("Final · 9 Nov 2026");
    const row = { id: "c", name: "MSA", counts: { points_open: 0 },
      negotiation_stage: { stage: "FINAL", since, days: 0 } } as unknown as Contract;
    const cell = renderToStaticMarkup(<CountsCell contract={row} viewer="owner" />);
    expect(cell).toContain("Final copy ready");
    expect(cell).not.toMatch(/point|change/);
  });
  it("a Final deal's tabs show one closed state, the points one click away", () => {
    const html = renderToStaticMarkup(<ClosedPanel what="points"><p>points</p></ClosedPanel>);
    expect(html).toContain("Nothing left to do");
    expect(html).toContain("Show the points");
    expect(html).not.toContain("<p>points</p>");
    expect(renderToStaticMarkup(<ClosedPanel what="changes" />)).toContain("upload their version");
  });
});
