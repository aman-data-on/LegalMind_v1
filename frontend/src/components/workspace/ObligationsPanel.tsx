"use client";

/**
 * Key Obligations — the assist lane's descriptive extraction: what each party
 * has to do, grouped under the DOCUMENT'S OWN role labels (e.g. "Customer",
 * "Provider"), each line pointing at the evidence it came from. Facts about
 * the text, never a judgment: nothing here says whether an obligation is
 * acceptable, risky or compliant — that is the evaluator's domain.
 *
 * Groups render stacked, not the reference's 2-up grid: this column is the
 * narrowest of the three, and a side-by-side grid would wrap every line.
 *
 * Flow: read what exists; when nothing was extracted yet, request the
 * extraction once (the server runs it synchronously — the Ask precedent) and
 * read again. Every failure is an honest quiet sentence — obligations are a
 * convenience, and their absence blocks nothing.
 */

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { ObligationGroup } from "@/lib/types";

import { useHighlight } from "./highlight";

type Load =
  | { kind: "loading" }
  | { kind: "extracting" }
  | { kind: "unavailable" }
  | { kind: "ready"; groups: ObligationGroup[] };

export function ObligationsPanel({ documentVersionId }: { documentVersionId: string }) {
  const [state, setState] = useState<Load>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    setState({ kind: "loading" });

    (async () => {
      try {
        const existing = await api.obligations(documentVersionId);
        if (cancelled) return;
        if (existing.extracted) {
          setState({ kind: "ready", groups: existing.groups });
          return;
        }
        setState({ kind: "extracting" });
        const attempt = await api.extractObligations(documentVersionId);
        if (cancelled) return;
        if (!attempt.extracted) {
          setState({ kind: "unavailable" });
          return;
        }
        const fresh = await api.obligations(documentVersionId);
        if (cancelled) return;
        setState({ kind: "ready", groups: fresh.groups });
      } catch {
        if (!cancelled) setState({ kind: "unavailable" });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [documentVersionId]);

  return (
    <section className="ws-analysis__section" aria-label="Key obligations">
      <h3 className="ws-analysis__title">Key obligations</h3>
      {state.kind === "loading" ? (
        <p className="ws-pane__note" aria-busy="true" role="status">
          Loading obligations…
        </p>
      ) : state.kind === "extracting" ? (
        <p className="ws-pane__note" aria-busy="true" role="status">
          Reading the document for each party&rsquo;s obligations…
        </p>
      ) : state.kind === "unavailable" ? (
        <p className="ws-pane__note">
          Obligations could not be extracted for this document. Everything else
          here still works.
        </p>
      ) : state.groups.length === 0 ? (
        <p className="ws-pane__note">No party obligations were identified in this document.</p>
      ) : (
        state.groups.map((group) => <ObligationGroupView key={group.party_label} group={group} />)
      )}
    </section>
  );
}

function ObligationGroupView({ group }: { group: ObligationGroup }) {
  const { point, target } = useHighlight();
  return (
    <div className="ws-obligations__group">
      {/* The document's own role label, verbatim — never a forced "us/them". */}
      <h4 className="ws-obligations__party">{group.party_label}</h4>
      <ul className="ws-obligations__list">
        {group.items.map((item) => (
          <li key={item.id} className="ws-obligations__item">
            <span className="ws-obligations__text">{item.obligation_text}</span>
            {item.evidence_id ? (
              <button
                type="button"
                className="ws-evidence__loc"
                aria-current={target === item.evidence_id ? "true" : undefined}
                onClick={() => point(item.evidence_id!, "the cited")}
              >
                {item.section_ref ? `§${item.section_ref}` : "View clause"}
                {item.page_number != null ? ` · p.${item.page_number}` : ""}
              </button>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
