/** Source integrity B1: the server's problems shown as they are — the UI decides nothing. */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { SourceProblems } from "@/components/workspace/SourceCheck";
import { SOURCE_CHECK } from "@/lib/labels";

const blocked = { problems: [{ code: "OLD_FIGURE", blocks: true, message: "Old figure: 99.95% is from the SLA.",
  current_wording: "Power | 99.9%" }], blocked: true, overridden: false, can_override: false };

describe("SourceProblems", () => {
  it("names each problem and the current wording, and says the copy check is a guard", () => {
    const html = renderToStaticMarkup(<SourceProblems result={blocked} onOverride={() => undefined} />);
    expect(html).toContain("Old figure: 99.95% is from the SLA.");
    expect(html).toContain("Power | 99.9%");
    expect(html).toContain(SOURCE_CHECK.blockedTitle);
    expect(html).toContain(SOURCE_CHECK.guardNote);
    expect(html).toContain(SOURCE_CHECK.askLegal);
    expect(html).not.toContain(SOURCE_CHECK.overrideButton);
    expect(html).not.toContain("OLD_FIGURE");            // never a code to a reader
  });

  it("offers the override only when the server says this reader may", () => {
    const html = renderToStaticMarkup(
      <SourceProblems result={{ ...blocked, can_override: true }} onOverride={() => undefined} />);
    expect(html).toContain(SOURCE_CHECK.overrideButton);
    expect(html).toContain(SOURCE_CHECK.overrideLabel);
    expect(html).not.toContain(SOURCE_CHECK.askLegal);
  });

  it("a warning only is copied and said as such", () => {
    const html = renderToStaticMarkup(<SourceProblems result={{ ...blocked, blocked: false,
      problems: [{ ...blocked.problems[0]!, blocks: false }] }} />);
    expect(html).toContain(SOURCE_CHECK.warnTitle);
  });
});
