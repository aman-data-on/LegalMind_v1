/**
 * What happens to a contract, in order — the Documents page's explainer strip.
 * Owner-supplied reference, 2026-09-01.
 *
 * ⚠️ THE COPY HERE IS NOT THE REFERENCE'S COPY, DELIBERATELY. The reference read
 * "AI extracts text and key clauses", "Contract type … identified", and
 * "Get risks, deviations & actionable insights". Each of those describes a
 * product LegalMind is specified NOT to be, and shipping it would have the
 * interface tell the user something the engine does not do:
 *
 * - `AI-01` (reaffirmed by `AM-25`): NO LLM, RAG, embedding or vector database in
 *   the AUTHORITATIVE analysis path. Extraction is deterministic. Calling it "AI
 *   extracts" would advertise the one architecture that is locked out.
 * - Owner Q9 (2026-08-19): Document Type is DECLARED by the uploader, NEVER
 *   inferred. `AM-34` (AB-7) lets the assist lane *suggest* one, and "only the
 *   human's confirmation records the type". So the type step is the user's, and
 *   the strip says so rather than promising automatic detection.
 * - Rule 12: a Finding reconstructs as Evidence → Fact → Standard → Rule →
 *   Result. "Risk" and "insight" are the vocabulary of a product that returns a
 *   score; this one returns a traceable chain, and the last step names that.
 * - Rule 9: the authoritative lane is deterministic — same inputs and the same
 *   configuration snapshot give the same result. That is the actual selling
 *   point, and it is stronger than "AI-powered".
 *
 * Step 3 is styled differently on purpose. Four of these five steps are things
 * the system does; one is a thing the reader does. Marking the human step is the
 * only ornament in the row, and it encodes something true rather than decorating
 * the sequence (the reference tinted steps 3 and 5 with no meaning attached).
 */

import {
  IconArrowRight,
  IconFileCheck,
  IconScale,
  IconScanText,
  IconTag,
  IconUploadCloud,
} from "@/components/workspace/icons";

type Step = {
  key: string;
  label: string;
  detail: string;
  icon: React.ReactNode;
  /** True for the one step the reader performs rather than watches. */
  yours?: boolean;
};

const STEPS: Step[] = [
  {
    key: "upload",
    label: "Upload",
    detail: "Stored once, never altered",
    icon: <IconUploadCloud size={20} />,
  },
  {
    key: "extract",
    label: "Extract",
    detail: "Every span kept as evidence",
    icon: <IconScanText size={20} />,
  },
  {
    key: "declare",
    // Two words, like every other label in the row. "You declare the type" read
    // better in isolation but wrapped to two lines at every width, which pushed
    // this step's detail text down and broke the row's shared baseline. The
    // ownership it was carrying now lives in the detail line and the ring.
    label: "Confirm type",
    detail: "You declare it",
    icon: <IconTag size={20} />,
    yours: true,
  },
  {
    key: "evaluate",
    label: "Evaluate",
    detail: "Against your approved standard",
    icon: <IconScale size={20} />,
  },
  {
    key: "findings",
    label: "Findings",
    detail: "Traced to the clause",
    icon: <IconFileCheck size={20} />,
  },
];

export function Pipeline() {
  return (
    <section className="ws-pipe" aria-labelledby="ws-pipe-title">
      <h2 id="ws-pipe-title" className="ws-visually-hidden">
        What happens to a contract after you upload it
      </h2>
      {/*
        An ordered list, because the order is the content — a screen reader
        announcing "1 of 5" is carrying the same information the arrows carry
        visually. The arrows are therefore decorative and hidden.
      */}
      <ol className="ws-pipe__row">
        {STEPS.map((step, index) => (
          <li
            key={step.key}
            className={`ws-pipe__step${step.yours ? " ws-pipe__step--yours" : ""}`}
          >
            <span className="ws-pipe__mark" aria-hidden="true">{step.icon}</span>
            <span className="ws-pipe__label">{step.label}</span>
            <span className="ws-pipe__detail">{step.detail}</span>
            {index < STEPS.length - 1 ? (
              <span className="ws-pipe__arrow" aria-hidden="true">
                <IconArrowRight size={15} />
              </span>
            ) : null}
          </li>
        ))}
      </ol>
      {/*
        The "documents stay on our own infrastructure" line is gone (owner,
        2026-09-01: essentials only). It was reassurance, not information someone
        acts on, and it sat in the one place on the page where a reader is trying
        to understand a sequence.

        Nothing about the fact changed — locked 54.6 and `AM-30` t1 still keep
        parsing, extraction and evaluation local. It is simply not this screen's
        job to say so, and a security claim in a workflow diagram reads as
        marketing whether or not it is true.
      */}
    </section>
  );
}
