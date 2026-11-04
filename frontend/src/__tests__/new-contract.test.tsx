/**
 * New contract (S5): a conditional question is asked only while its condition holds, an
 * approved-options question is a set of choices (never free text), each value in the
 * preview takes you to its question, a stale save is a conflict (never an overwrite), and
 * with no published template the page says why in plain words.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

const session = { can: (_p: string) => false };
vi.mock("@/lib/session", () => ({ useSession: () => session }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }), useSearchParams: () => new URLSearchParams() }));

import NewContractPage from "@/app/contracts/new/page";
import { ContractPreview } from "@/components/newcontract/ContractPreview";
import { ConflictBanner, NoTemplate, saveOnce } from "@/components/newcontract/NewContract";
import { QuestionField } from "@/components/newcontract/QuestionField";
import { ApiError } from "@/lib/api";
import {
  clientFieldError, dateText, display, evaluate, groups, outsideRange, parseDate, profileValue, NO_CLOUDPE_MSA, problemWords, toAnswers, unanswered, unavailable,
  visibleQuestions, type ContractModel, type Draft, type PublishedTemplate, type Question,
} from "@/lib/newContract";

const questions: Question[] = [
  { key: "effective_date", label: "Effective date", type: "date", group: "Deal", class: "M" },
  { key: "our_name", label: "Our name", type: "text", group: "Our company", class: "M", locked_value: "LeapSwitch Networks Pvt Ltd" },
  { key: "term_years", label: "Term (years)", type: "int", group: "Deal", class: "M", range: [1, 3] },
  { key: "venue", label: "Venue", type: "choice", group: "Legal", class: "AO", allowed: ["Pune", "Mumbai"] },
  { key: "personal_data", label: "Personal data is processed", type: "bool", group: "Legal", class: "M" },
  { key: "dpa_contact", label: "Data protection contact", type: "text", group: "Legal", class: "C",
    when: { "==": [{ var: "personal_data" }, true] } },
  { key: "notes", label: "Reference", type: "text", group: "Deal", class: "O" },
];

const template = (over: Partial<PublishedTemplate> = {}): PublishedTemplate => ({
  id: "tv-1", template_key: "NDA.LEAPSWITCH", version: 1, doc_type: "NDA", brand: "LEAPSWITCH",
  title: "NON-DISCLOSURE AGREEMENT", questions, annexures: [], ...over,
});

describe("conditional questions", () => {
  it("are asked only while their condition holds, the way the server reads it", () => {
    expect(visibleQuestions(questions, {}).map((q) => q.key)).not.toContain("dpa_contact");
    expect(visibleQuestions(questions, { personal_data: false }).map((q) => q.key)).not.toContain("dpa_contact");
    expect(visibleQuestions(questions, { personal_data: true }).map((q) => q.key)).toContain("dpa_contact");
    expect(evaluate({ and: [{ ">=": [{ var: "n" }, 2] }, { in: [{ var: "v" }, ["Pune"]] }] }, { n: 3, v: "Pune" })).toBe(true);
    expect(evaluate({ "<": [{ var: "missing" }, 3] }, {})).toBe(false);      // a missing variable is never true
  });

  it("ask the client first and our side last; any other group in the template's order", () => {
    expect(groups(questions, {}).map((g) => g.name)).toEqual(["Deal", "Legal", "Our company"]);
    const client: Question = { key: "party_two_name", label: "Client's legal name", group: "Client" };
    expect(groups([...questions, client], {}).map((g) => g.name)).toEqual(["Client", "Deal", "Legal", "Our company"]);
  });

  it("read a date as India writes it, day first, and never send a half-typed one", () => {
    expect(parseDate("10/11/2026")).toBe("2026-11-10");
    expect(parseDate("1-2-2027")).toBe("2027-02-01");
    expect(parseDate("2026-11-10")).toBe("2026-11-10");
    expect(parseDate("31/02/2026")).toBeNull();
    expect(parseDate("10/11")).toBeNull();
    expect(dateText("2026-11-10")).toBe("10/11/2026");
    expect(toAnswers(questions, { effective_date: "10/11" })).toEqual({});
    expect(unanswered(questions, { effective_date: "10/11" }).map((q) => q.key)).toContain("effective_date");
  });

  it("say when a number is outside the template, and what to do instead", () => {
    expect(outsideRange(questions[2]!, "2")).toBeNull();
    expect(outsideRange(questions[2]!, "5")).toMatch(/allows a number between 1 and 3\. A different number needs Legal/);
  });

  it("know a value that came from the client profile, by its field", () => {
    const q: Question = { key: "party_two_cin", label: "Client's CIN or LLPIN", profile_field: "cin_or_llpin" };
    expect(profileValue({ cin_or_llpin: "U72900MH2010PTC123456" }, q)).toBe("U72900MH2010PTC123456");
    const name: Question = { key: "party_two_name", label: "Client's legal name", profile_field: "legal_name" };
    expect(profileValue({ name: "Acme" }, name)).toBe("Acme");
    expect(profileValue(null, q)).toBeNull();
    const html = renderToStaticMarkup(<QuestionField q={q} value="U72900MH2010PTC123456" onChange={() => {}}
                                                     profile={{ value: "U72900MH2010PTC123456", onUpdate: () => {} }} />);
    expect(html).toContain("From the client profile");
    const changed = renderToStaticMarkup(<QuestionField q={q} value="AAB-1234" onChange={() => {}}
                                                        profile={{ value: "U72900MH2010PTC123456", onUpdate: () => {} }} />);
    expect(changed).toContain("Also update the client profile");
  });

  it("send only what is asked: no fixed value, no hidden answer, nothing empty, numbers as numbers", () => {
    const sent = toAnswers(questions, { our_name: "Other Ltd", term_years: "2", dpa_contact: "dpo@x.in",
                                        personal_data: false, notes: "  ", venue: "Pune" });
    expect(sent).toEqual({ term_years: 2, personal_data: false, venue: "Pune" });
  });

  it("list what is still required, in the current shape of the form", () => {
    const left = (a: Record<string, unknown>) => unanswered(questions, a).map((q) => q.key);
    expect(left({})).toEqual(["effective_date", "term_years", "venue", "personal_data"]);
    expect(left({ effective_date: "2026-11-10", term_years: 2, venue: "Pune", personal_data: true })).toEqual(["dpa_contact"]);
  });
});

describe("approved options", () => {
  it("are choices, never a free-text box", () => {
    const html = renderToStaticMarkup(<QuestionField q={questions[3]!} value="Pune" onChange={() => {}} />);
    expect(html).toContain('type="radio"');
    expect(html).not.toContain('type="text"');
    expect(html).toContain("Pune");
    expect(html).toContain("Mumbai");
    expect(html).toContain("Required");
  });

  it("a fixed value is text, never an input; a number says its range", () => {
    const fixed = renderToStaticMarkup(<QuestionField q={questions[1]!} value={undefined} onChange={() => {}} />);
    expect(fixed).toContain("Fixed by our template");
    expect(fixed).not.toContain("<input");
    const n = renderToStaticMarkup(<QuestionField q={questions[2]!} value="2" onChange={() => {}} />);
    expect(n).toMatch(/min="1"/);
    expect(n).toMatch(/max="3"/);
    expect(n).toContain("Between 1 and 3");
  });
});

describe("the preview", () => {
  const model: ContractModel = {
    title: "NON-DISCLOSURE AGREEMENT",
    preamble: [{ t: "Made on " }, { t: "1 January 2000", var: "effective_date" }, { t: " by " },
               { t: "LeapSwitch Networks Pvt Ltd", var: "our_name" }, { t: "." }],
    parties: [], recitals: [],
    body: [{ clause_key: "TERM", number: "1", title: "Term", body: [
      { kind: "sub", number: "1.1", runs: [{ t: "For " }, { t: "[Term (years)]", var: "term_years" }, { t: " years, see " },
                                          { ref: "VENUE", num: "2" }, { t: "." }], body: [] }] }],
    schedules: [], execution: { rows: [], seal: false, witness: false },
  };

  it("links every value to its question and names what is missing; fixed text is plain", () => {
    const html = renderToStaticMarkup(
      <ContractPreview model={model} questions={questions} local={{ effective_date: "2026-11-10" }} onJump={() => {}} />);
    expect(html).toContain("10 November 2026");                         // the reader's own value, as typed
    expect(html).toMatch(/<button[^>]*class="nc-val"[^>]*aria-label="10 November 2026 — Effective date\. Go to the question"/);
    expect(html).toMatch(/<button[^>]*class="tpl-field nc-hole"[^>]*>Term \(years\)<\/button>/);
    expect(html).not.toMatch(/<button[^>]*>LeapSwitch Networks Pvt Ltd/);  // our fixed text is not a control
    expect(html).toContain("1.1");
    expect(html).not.toMatch(/contenteditable|<textarea/i);               // no editor on the sheet
  });

  it("prints a value the way the contract does", () => {
    expect(display(questions[0], "2026-01-05")).toBe("5 January 2026");
    expect(display(questions[4], true)).toBe("Yes");
  });
});

describe("saving", () => {
  const draft = { id: "d-1", version: 4 } as Draft;

  it("a stale version is a conflict, never an overwrite", async () => {
    const stale = vi.fn().mockRejectedValue(new ApiError(409, "CONFLICT", "changed elsewhere", "r"));
    expect(await saveOnce("d-1", {}, 3, stale)).toEqual({ kind: "conflict" });
    expect(stale).toHaveBeenCalledWith("d-1", {}, 3);
    expect(await saveOnce("d-1", {}, 4, vi.fn().mockResolvedValue(draft))).toEqual({ kind: "saved", draft });
    expect((await saveOnce("d-1", {}, 4, vi.fn().mockRejectedValue(new ApiError(500, "X", "boom", "r")))).kind).toBe("error");
  });

  it("the conflict says what happened and offers the reload", () => {
    const html = renderToStaticMarkup(<ConflictBanner onReload={() => {}} />);
    expect(html).toContain("saved in another tab or window");
    expect(html).toContain("Reload the answers");
  });

  it("a server problem reads as the question's label; our own rendering's is for Legal", () => {
    expect(problemWords({ field: "term_years", problem: "must be between 1 and 3" }, questions).text)
      .toBe("Term (years) must be between 1 and 3");
    expect(problemWords({ field: "preflight UNDEFINED_TERM", problem: "x" }, questions).text).toMatch(/Tell Legal/);
    expect(clientFieldError("cin_or_llpin")).toMatch(/not a CIN/);
  });
});

describe("no published template", () => {
  it("says which template, in plain words; CloudPe MSA in the Constitution's words", () => {
    expect(unavailable("NDA", "CLOUDPE", [template()])).toBe("Our CloudPe NDA template is being approved by Legal.");
    expect(unavailable("NDA", "LEAPSWITCH", [template()])).toBeNull();
    expect(unavailable("MSA", "CLOUDPE", [template({ doc_type: "MSA", brand: "CLOUDPE" })])).toBe(NO_CLOUDPE_MSA);
  });

  it("offers the upload, and Templates only to who may approve them", () => {
    const reason = unavailable("MSA", "LEAPSWITCH", [])!;
    const seller = renderToStaticMarkup(<NoTemplate reason={reason} approver={false} onUpload={() => {}} />);
    expect(seller).toContain("Our LeapSwitch MSA template is being approved by Legal.");
    expect(seller).toContain("Upload a contract");
    expect(seller).not.toContain("Templates");
    expect(renderToStaticMarkup(<NoTemplate reason={reason} approver onUpload={() => {}} />)).toContain('href="/templates"');
  });

  it("the page is absent for a reader who may not create a contract", () => {
    session.can = () => false;
    expect(renderToStaticMarkup(<NewContractPage />)).toContain("Page not found");
  });
});
