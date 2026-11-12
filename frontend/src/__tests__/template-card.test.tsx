/**
 * `AM-316` — a template says its name, purpose and the points it sends to Legal on every
 * deal; New contract asks "Which MSA?" only when two or more are usable, preselects only
 * from a deep link, never offers one awaiting approval, and step 3 splits the template's
 * points from what the answers moved.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/session", () => ({ useSession: () => ({ can: () => false }) }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }), useSearchParams: () => new URLSearchParams() }));

import { StepOne } from "@/components/newcontract/NewContract";
import { TemplateCard } from "@/components/templates/TemplateCard";
import { splitPoints, type PublishedTemplate } from "@/lib/newContract";
import { legalLine, statusWords, stopCount, templatesFor, type TemplateCheck, type TemplateSummary } from "@/lib/templates";

const msa = (over: Partial<PublishedTemplate>): PublishedTemplate => ({
  id: "t1", template_key: "MSA.A", version: 1, doc_type: "MSA", brand: "LEAPSWITCH", title: "MASTER SERVICES AGREEMENT",
  published_at: "2026-11-09T10:00:00+05:30", questions: [], annexures: [], ...over,
});
const original = msa({ id: "t1", template_key: "MSA.ORIGINAL", name: "LeapSwitch MSA — Original", purpose: "As signed off.",
  recommended: true, known_points: [{ code: "LIABILITY-MSA-001", name: "LIABILITY-MSA-001", classification: "CONFLICT" },
    { code: "INDEMNITY-MSA-001", name: "INDEMNITY-MSA-001", classification: "DEVIATION" }] });
const newer = msa({ id: "t2", template_key: "MSA.NEW", name: "LeapSwitch MSA — 2026", known_points: [], published_at: "2026-11-10T10:00:00+05:30" });
const awaiting = msa({ id: "t3", template_key: "MSA.NEW", version: 6, name: "LeapSwitch MSA — 2027", awaiting_approval: true, published_at: null });
const step = (published: PublishedTemplate[], wanted: string | null, waiting = [] as PublishedTemplate[]) =>
  renderToStaticMarkup(<StepOne published={published} awaiting={waiting} wanted={wanted} onStart={async () => undefined} />);

describe("the template's own words", () => {
  it("says the points in one line, and nothing when none are declared", () => {
    expect(legalLine(undefined)).toBeNull();
    expect(legalLine([])).toBe("Nothing goes to Legal unless your details change it.");
    expect(legalLine([{ code: "A" }])).toBe("1 point goes to Legal on every deal");
    expect(legalLine([{ code: "A" }, { code: "B" }])).toBe("2 points go to Legal on every deal");
  });

  it("lists Legal's recommended template first and never one awaiting approval", () => {
    expect(templatesFor([newer, awaiting, original], "MSA", "LEAPSWITCH").map((t) => t.id)).toEqual(["t1", "t2"]);
  });

  it("names the radio by the template alone; the points and the download sit outside its label", () => {
    const html = renderToStaticMarkup(<TemplateCard t={original} radio={{ name: "x", checked: false, onChange: () => undefined }} actions={<button>Download blank</button>} />);
    const label = /<label[^>]*>([\s\S]*?)<\/label>/.exec(html)![1]!;
    expect(label).not.toMatch(/<details|<button|<a /);
    expect(html).toMatch(/aria-labelledby="[^"]+-n"/);
    expect(html).toMatch(/aria-describedby="[^"]+-p [^"]+-l [^"]+-r"/);
    expect(html).toContain("2 points go to Legal on every deal");
    expect(html).toContain("See the 2 points");
    expect(html).toContain("Legal recommends this one");
    expect(html).not.toMatch(/-MSA-0|\.docx|MSA\.ORIGINAL/);
  });
});

describe("New contract, step 1", () => {
  it("asks which MSA only with two usable, preselecting nothing but a deep link's", () => {
    const html = step([original, newer], "MSA.NEW");
    expect(html).toContain("Which MSA?");
    expect((html.match(/name="nc-template"/g) ?? []).length).toBe(2);
    expect((html.match(/name="nc-template" checked=""/g) ?? []).length).toBe(1);
    expect(step([original, newer], null)).not.toContain("Which MSA?");       // nothing chosen yet
  });

  it("shows the one template as “Our template”, and one awaiting approval only as a line", () => {
    const html = step([original], "MSA.ORIGINAL", [awaiting]);
    expect(html).not.toContain("Which MSA?");
    expect(html).toContain("Our template");
    expect(html).toContain("A new MSA is awaiting approval.");
    expect(html).not.toContain("2027");
  });

  it("says when a deep link names a template no longer published", () => {
    expect(step([original], "MSA.GONE")).toContain("That template is not published any more. Choose one below.");
  });
});

describe("step 3", () => {
  it("splits the template's points from what the answers moved, showing only what the check found", () => {
    const found = [{ code: "LIABILITY-MSA-001" }, { code: "PAYMENT-PERIOD-MSA-001" }];
    const { fromTemplate, fromDetails } = splitPoints(found, original.known_points);
    expect(fromTemplate.map((p) => p.code)).toEqual(["LIABILITY-MSA-001"]);
    expect(fromDetails.map((p) => p.code)).toEqual(["PAYMENT-PERIOD-MSA-001"]);   // moved by an answer
  });
});

describe("before publishing", () => {
  it("counts a declared point as no problem, and says the points beside Ready to publish", () => {
    const std = (code: string, over = {}) => ({ code, description: code, classification: "DEVIATION", clause_keys: [], ...over });
    const check: TemplateCheck = { publishable: true, problems: [], known_points: ["LIABILITY-MSA-001"], stale: [],
      standards: [std("LIABILITY-MSA-001", { in_our_favour: true, to_legal: true }), std("PAYMENT-PERIOD-MSA-001", { in_our_favour: true, to_legal: false })] };
    expect(stopCount(check)).toBe(0);
    const t = { status: "DRAFT", clauses_total: 2, clauses_approved: 2, version: 6 } as TemplateSummary;
    expect(statusWords(t, check)).toBe("Ready to publish. 1 point will go to Legal on every deal");
    expect(stopCount({ ...check, known_points: [], stale: ["X"] })).toBe(2);       // undeclared + stale
  });
});
