import { describe, expect, it, vi } from "vitest";

import { isRewritten, sentences, tidyTitle } from "@/components/diff-talk/text";
import { loadChoices } from "@/components/diff-talk/useChoices";
import { api, ApiError } from "@/lib/api";

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

  it("calls a clause rewritten by its words, not its sentences", () => {
    const clause = (text: string) => ({ id: text, ref: null, title: null, text });
    const fees = clause("Fees are payable within fifteen days of invoice.");
    // One sentence, one word changed: an edit, shown with word marks.
    expect(isRewritten(fees, clause("Fees are payable within forty-five days of invoice."))).toBe(false);
    // The same subject in the client's own words: two plain texts.
    expect(isRewritten(fees, clause("The customer shall settle each bill no later than one month after it is issued."))).toBe(true);
  });
});

describe("Diff-Talk choices kept in this browser", () => {
  const stored = { A: { choice: "ours" as const, decided_by: "Aman", decided_by_me: true, updated_at: "" } };

  it("a refused bring-over shows what is stored, says so, and is not retried", async () => {
    const store = new Map([["diff-talk:choices:v2:l|r", JSON.stringify({ B: "theirs" })]]);
    vi.stubGlobal("window", { localStorage: {
      getItem: (k: string) => store.get(k) ?? null, removeItem: (k: string) => store.delete(k) } });
    vi.spyOn(api, "comparisonChoices").mockResolvedValue({ can_choose: true, choices: {} });
    vi.spyOn(api, "setComparisonChoices")
      .mockRejectedValue(new ApiError(422, "BUSINESS_RULE", "too many choices", "-"));
    const got = await loadChoices("l", "r");
    expect(got.canChoose).toBe(true);           // the reader can still choose
    expect(got.error).toMatch(/could not be brought over/);
    expect(store.size).toBe(0);                 // refused once is refused always
    vi.spyOn(api, "comparisonChoices").mockResolvedValue({ can_choose: true, choices: stored });
    expect((await loadChoices("l", "r")).choices).toEqual(stored);
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });
});
