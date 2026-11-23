"use client";

import { answered, display, OURS, type Answers, type Question } from "@/lib/newContract";

/** Our side in one line (`Our company`): the entity our template fixes and who signs.
 *  Change opens the questions; a value our template fixes stays fixed inside. */
export function OurCompany({ questions, local, open, onOpen, children }: {
  questions: Question[]; local: Answers; open: boolean; onOpen: (open: boolean) => void; children: React.ReactNode;
}) {
  const by = (role: string) => questions.find((q) => q.role === role || q.key === role);
  const name = by("our_name");
  const signer = by("our_signatory_name");
  const title = by("our_signatory_designation");
  const signs = signer && answered(signer, local[signer.key]) ? String(local[signer.key]) : null;
  const as = title && answered(title, local[title.key]) ? String(local[title.key]) : null;
  const missing = questions.filter((q) => (q.class ?? "M") !== "O" && q.locked_value === undefined && !answered(q, local[q.key]));
  // E2E 6f: a signatory fixed by our template is shown, never offered as a choice
  const fixed = questions.filter((q) => (q.class ?? "M") !== "O").every((q) => q.locked_value !== undefined);
  return (
    <section className="nc-group nc-ours" aria-labelledby="nc-g-ours">
      <h2 id="nc-g-ours" className="nc-sub">{OURS}</h2>
      <div className="nc-ours__line">
        <div>
          <p className="nc-item__l1">{name ? display(name, name.locked_value ?? local[name.key]) : "Our company"}</p>
          <p className="nc-item__l2">
            {signs ? `Signed by ${signs}${as ? `, ${as}` : ""}`
              : missing.length ? `${missing[0]!.label} is not chosen yet` : "Fixed by our template"}
          </p>
        </div>
        <button type="button" className="ws-btn ws-btn--sm" aria-expanded={open} aria-controls="nc-ours-fields"
                onClick={() => onOpen(!open)}>{open ? "Done" : fixed ? "See who signs" : signs ? "Change" : "Choose who signs"}</button>
      </div>
      {open ? <div id="nc-ours-fields" className="nc-group">{children}</div> : null}
    </section>
  );
}
