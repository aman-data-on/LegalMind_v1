/**
 * One Finding, with its Evaluations always attached — locked 49.7 r1, 52.5.
 *
 * Two structural properties, both deliberate:
 *
 * 1. **`classification` and `evaluations` are rendered together, always.** There
 *    is no prop that collapses this to a single verdict. Locked 52.5: "A Finding
 *    row shows its derived `classification` **and** is expandable to its
 *    Evaluations. It is never presented as a single verdict." Because the
 *    component has no way to omit them, the "hidden carve-out" failure — an
 *    aggregate cap that conforms, masking an exception that does not — cannot be
 *    reached from here.
 *
 * 2. **There is no Finding-level decision control and no resolve control.** This
 *    component accepts no decision props at all. Decisions attach to the
 *    Evaluation (AB-1, 49.7, 52.5), and resolution is derived server-side, never
 *    asserted by a caller (D-3.6, Step 30 r3/r16). A Finding cannot be resolved
 *    from this UI because there is nothing here to do it with.
 *
 * `RESOLVED ≠ MATCH` (rule 14, Step 30 r8): status and classification are shown
 * as two separate values, so a resolved Finding still displays the classification
 * it was given.
 */

import { EvaluationRow } from "./EvaluationRow";
import { StatePill } from "./Primitives";
import { EvidenceList } from "./EvidenceList";
import type { Evaluation, Finding } from "@/lib/types";

export function FindingCard({
  finding,
  renderEvaluationActions,
  children,
  current = false,
}: {
  finding: Finding;
  /** Per-Evaluation decision UI, injected by the Review screen. */
  renderEvaluationActions?: (evaluation: Evaluation) => React.ReactNode;
  /** Escalation controls, which are Finding-level (F-3, AM-23). */
  children?: React.ReactNode;
  /** Marks where keyboard navigation (n/p) currently points. Presentation only. */
  current?: boolean;
}) {
  return (
    <article
      /* Attention edge from the server-provided flag — never derived here (52.7). */
      className={`finding${finding.requires_decision ? " finding--attention" : ""}${
        current ? " finding--current" : ""
      }`}
      data-finding-id={finding.id}
      /* Focusable by script only (n/p navigation), never in the Tab order — Tab
         still walks the real controls inside the card. */
      tabIndex={-1}
    >
      <header className="finding__head">
        <h3 className="finding__requirement">
          {finding.requirement.code ?? "Requirement"}
          {finding.requirement.name ? ` — ${finding.requirement.name}` : ""}
        </h3>

        <div className="finding__states">
          {/*
            Derived summary (49.7 r1, D-1.1). Labelled as such so it is not read
            as the authoritative result — the Evaluations below are.
          */}
          <StatePill
            axis="classification"
            value={finding.classification}
            title="Derived summary of the Evaluations below"
          />

          {/*
            A separate axis from classification (REC-06). Rendering them side by
            side is what keeps RESOLVED ≠ MATCH visible: a RESOLVED Finding still
            shows DEVIATION here.
          */}
          <StatePill axis="status" value={finding.status} />

          {finding.escalated ? (
            <StatePill axis="status" value="Escalated" title="Requires authorized review" />
          ) : null}
        </div>
      </header>

      <p className="finding__note">
        Classification is a derived summary. The scoped Evaluations below are the
        authoritative results.
      </p>

      <ol className="evaluations">
        {finding.evaluations.map((evaluation) => (
          <EvaluationRow key={evaluation.id} evaluation={evaluation}>
            {renderEvaluationActions?.(evaluation)}
          </EvaluationRow>
        ))}
      </ol>

      {finding.evaluations.length === 0 ? (
        /*
         * EV-MIN (AB-1.6) makes this unreachable: every Finding has at least one
         * Evaluation, enforced by a database constraint trigger. Shown as a defect
         * rather than as an empty state, because silently rendering a Finding with
         * no Evaluations would present the derived summary alone — the exact thing
         * 49.7 r1 forbids.
         */
        <p className="error">
          This Finding has no Evaluations, which should not be possible. Do not rely
          on the classification above; report this.
        </p>
      ) : null}

      <EvidenceList evidence={finding.evidence} />

      {children}
    </article>
  );
}
