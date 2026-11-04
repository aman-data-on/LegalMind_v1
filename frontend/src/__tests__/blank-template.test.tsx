/** `AM-302`: the blank template and the review copy as a menu button (WAI-ARIA APG), a
 *  quiet link on New contract, the paths the server serves, and the Changes page's words
 *  for a copy that came back from a template. */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { DownloadMenu, menuMove } from "@/components/templates/DownloadMenu";
import { oursLabel, type ChangeList } from "@/lib/changes";
import { BLANK_NOTE, blankPath, reviewCopyPath } from "@/lib/templates";

describe("DownloadMenu", () => {
  it("is an icon menu button named by its label, with a tooltip and the download glyph", () => {
    const html = renderToStaticMarkup(<DownloadMenu path="/templates/MSA.X/blank" label="Download blank template" />);
    expect(html).toContain('aria-haspopup="menu"');
    expect(html).toContain('aria-expanded="false"');
    expect(html).toContain('aria-label="Download blank template"');
    expect(html).toMatch(/class="tpl-dl__tip" aria-hidden="true">Download blank template</);
    expect(html).toContain("lucide-download");
    expect(html).not.toContain('role="menu"');           // closed until asked
    expect(html).toContain('role="status"');              // where "Preparing PDF…" is said
  });

  it("as a link shows its words and needs no aria-label", () => {
    const html = renderToStaticMarkup(
      <DownloadMenu variant="link" align="start" path="/templates/MSA.X/blank" label="Download blank copy" />);
    expect(html).toContain("<span>Download blank copy</span>");
    expect(html).not.toContain("aria-label=");
    expect(html).not.toContain("tpl-dl__tip");
  });

  it("moves through the menu as the APG says: arrows wrap, Home and End jump", () => {
    expect(menuMove("ArrowDown", 0, 2)).toBe(1);
    expect(menuMove("ArrowDown", 1, 2)).toBe(0);
    expect(menuMove("ArrowUp", 0, 2)).toBe(1);
    expect(menuMove("Home", 1, 2)).toBe(0);
    expect(menuMove("End", 0, 2)).toBe(1);
    expect(menuMove("a", 0, 2)).toBeNull();
  });
});

describe("paths and words", () => {
  it("names the blank by key and the review copy by id", () => {
    expect(blankPath({ template_key: "MSA.LEAPSWITCH" })).toBe("/templates/MSA.LEAPSWITCH/blank");
    expect(reviewCopyPath({ id: "t-1" })).toBe("/templates/t-1/review-copy");
    expect(BLANK_NOTE).toBe("For filling outside LegalMind. Upload what you send or sign, so we can check it.");
  });

  it("calls the left side our template when the copy came from one", () => {
    const base: Pick<ChangeList, "from" | "template"> = { from: null };
    expect(oursLabel({ ...base, from: { document_version_id: "v", version_number: 2 } })).toBe("Ours, version 2");
    expect(oursLabel({ ...base, template: { template_key: "K", version: 2, title: null, how: "id",
      current_version: 3, older: true, message: "Made from an older template (v2); the current one is v3." } }))
      .toBe("Our template, version 2");
  });
});
