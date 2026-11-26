import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { Row, said, withoutHeading } from "@/components/workspace/OurPaper";
import { OUR_PAPER_COPY } from "@/lib/labels";
import type { PaperRow } from "@/lib/ourPaper";

const base = { source: "3.1", doc: "MSA", mode: "NUMBERED", number: "17.2", sub: null, title: null, described: null,
               verb: "REPLACES", client_quote: "This replaces MSA clause 17.2." } as const;

describe("AM-476 what it replaces in our paper (display only)", () => {
  it("says the client's verb on our clause, quotes ours and a marker, and no direction words", () => {
    const row = { ...base, status: "RESOLVED", ours: { title: "Cap", quote: "17.2. Cap: Placeholder text." }, markers: ["AS IS"] } as PaperRow;
    const html = renderToStaticMarkup(<Row row={row} />).replaceAll("<!-- -->", "");
    expect(html).toContain("Replaces our MSA clause 17.2.");
    expect(html).toContain(">Placeholder text.<");                   // the heading is not said twice
    expect(html).toContain("Our text contains «AS IS».");
    expect(html).not.toContain("SHA-256");                            // the pin is said once, above
    expect(html.toLowerCase()).not.toMatch(/favour|worse|better|risk|helps|hurts/);
  });

  it("phrases each verb as the client's own", () => {
    expect(said({ ...base, verb: "DOES_NOT_APPLY", number: "16.1.1" } as unknown as PaperRow)).toBe("Says our MSA clause 16.1.1 does not apply.");
    expect(said({ ...base, verb: "INCLUDES", number: "21.3" } as unknown as PaperRow)).toBe("Says our MSA clause 21.3 includes it.");
    expect(said({ ...base, doc: "TOS", verb: "DESPITE", number: "5" } as unknown as PaperRow)).toBe("Applies despite our Terms of Service section 5.");
  });

  it("says why a reference was not looked up, offers Legal the pick, and shows no quote of ours", () => {
    const html = renderToStaticMarkup(<Row row={{ ...base, status: "WHICH_MSA" } as PaperRow} onPick={() => {}} />);
    expect(html).toContain("Which MSA? Legal picks the one this refers to.");
    expect(html).toContain(">Pick the MSA</button>");
    expect(html).not.toContain("Ours");
  });

  it("words the brief line per document and strips a repeated heading", () => {
    expect(OUR_PAPER_COPY.brief({ MSA: 18 })).toBe("The client's paper replaces or overrides 18 clauses of our MSA.");
    expect(OUR_PAPER_COPY.brief({ MSA: 18, TOS: 1 })).toBe("The client's paper replaces or overrides 18 clauses of our MSA and 1 of our Terms of Service.");
    expect(withoutHeading("21.3. Entire Agreement: This Agreement…", "21.3", "Entire Agreement")).toBe("This Agreement…");
  });
});
