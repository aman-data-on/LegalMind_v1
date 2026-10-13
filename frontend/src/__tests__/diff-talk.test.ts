import { describe, expect, it } from "vitest";

import { sentences, tidyTitle } from "@/components/workspace/DiffTalk";

describe("Diff-Talk sentence layout", () => {
  it("re-sets PDF line breaks as one sentence per line", () => {
    expect(sentences("Fees are billed\nmonthly. Invoices are\n  due in 15 days.")).toBe(
      "Fees are billed monthly.\nInvoices are due in 15 days.");
  });

  it("rejoins a word hyphenated across a PDF line", () => {
    expect(sentences("any authority or quasi-\ngovernmental body.")).toBe(
      "any authority or quasi-governmental body.");
  });

  it("never ends a sentence at a list number, an initial or a company abbreviation", () => {
    expect(sentences("Leapswitch Networks Pvt. Ltd. (\"Leapswitch\") agrees. 1. To apply, e.g. by J. Smith."))
      .toBe("Leapswitch Networks Pvt. Ltd. (\"Leapswitch\") agrees.\n1. To apply, e.g. by J. Smith.");
  });


  it("shows ALL-CAPS clause headings in title case, and leaves the rest alone", () => {
    expect(tidyTitle("1. DEFINITIONS")).toBe("1. Definitions");
    expect(tidyTitle("SCHEDULE A DATA HOSTING AND EXIT")).toBe("Schedule A Data Hosting and Exit");
    expect(tidyTitle("CUSTOMER’S RESPONSIBILITIES")).toBe("Customer’s Responsibilities");
    expect(tidyTitle("Late Fees")).toBe("Late Fees");
    expect(tidyTitle("KYC")).toBe("KYC");
  });
});
