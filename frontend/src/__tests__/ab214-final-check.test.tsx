/** AM-413 r5: a final contract whose own check failed says so on the Contract tab. */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

const state = { kind: "failed" as string };
vi.mock("@/components/workspace/findingsState", () => ({
  useFindingsStateOptional: () => ({ state, reload: () => {}, refresh: () => {} }),
}));

import { FinalCheckFailed } from "@/components/workspace/FinalCopy";
import { ScBadge } from "@/components/templates/TemplateList";

describe("a final contract whose check failed", () => {
  const final = { id: "v", package: { of_version_id: "x" }, final_copy: undefined } as never;
  it("shows the error with Try again — only for a final, only when the check failed", () => {
    state.kind = "failed";
    const html = renderToStaticMarkup(<FinalCheckFailed version={final} />);
    expect(html).toContain("The final contract could not be checked");
    expect(html).toContain("Try again");
    expect(html).toContain('role="alert"');
    expect(renderToStaticMarkup(<FinalCheckFailed version={{ id: "v" } as never} />)).toBe("");
    state.kind = "ready";
    expect(renderToStaticMarkup(<FinalCheckFailed version={final} />)).toBe("");
  });
  it("the template card names Annexure 2 where the contract does", () => {
    expect(renderToStaticMarkup(<ScBadge two readiness={{ ready: true, missing: [] }} />)).toContain("Annexure 2 set up");
  });
});
