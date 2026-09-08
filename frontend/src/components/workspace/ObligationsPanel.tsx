"use client";

/**
 * Key Obligations — the assist lane's descriptive extraction: what each party
 * has to do, grouped under the DOCUMENT'S OWN role labels (e.g. "Customer",
 * "Provider"), each line pointing at the evidence it came from. Facts about
 * the text, never a judgment: nothing here says whether an obligation is
 * acceptable, risky or compliant — that is the evaluator's domain.
 *
 * Categories render as a single-open accordion (owner, 2026-09-08): the
 * side-by-side columns left one long party's list dictating the height of the
 * whole section, with the rest of the row empty. `obligationCategories` does
 * the label work — see its note on why "our side / their side" is not
 * synthesised from a role label.
 *
 * Flow: read what exists; when nothing was extracted yet, request the
 * extraction once (the server runs it synchronously — the Ask precedent) and
 * read again. Every failure is an honest quiet sentence — obligations are a
 * convenience, and their absence blocks nothing.
 */

import { useEffect, useId, useState } from "react";
import { sectionRef } from "@/lib/documentTypes";

import { api } from "@/lib/api";
import type { ObligationGroup, ObligationItem } from "@/lib/types";

import { useHighlight } from "./highlight";
import { IconCheckCircle, IconChevronDown, IconChevronUp } from "./icons";
import { obligationCategories } from "./model";

type Load =
  | { kind: "loading" }
  | { kind: "extracting" }
  | { kind: "unavailable" }
  | { kind: "ready"; groups: ObligationGroup[] };

/** Items shown per party before "View all" expands the list. */
const OBLIGATIONS_SHOWN = 5;

export function ObligationsPanel({ documentVersionId }: { documentVersionId: string }) {
  const [state, setState] = useState<Load>({ kind: "loading" });
  const [expanded, setExpanded] = useState(false);
  /** null = "the first category", the sensible default; "" = the user closed it. */
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setState({ kind: "loading" });
    setOpen(null);
    setExpanded(false);

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

  const categories = state.kind === "ready" ? obligationCategories(state.groups) : [];
  const openKey = open === null ? categories[0]?.key : open;
  const openCategory = categories.find((category) => category.key === openKey);

  return (
    <section className="ws-analysis__section" aria-label="Key obligations">
      <div className="ws-analysis__head">
        <h3 className="ws-analysis__title">Key obligations</h3>
        {openCategory && openCategory.items.length > OBLIGATIONS_SHOWN ? (
          <button type="button" className="ws-viewall" onClick={() => setExpanded((v) => !v)}>
            {expanded ? "Show fewer" : "View all"}
          </button>
        ) : null}
      </div>
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
      ) : categories.length === 0 ? (
        <p className="ws-pane__note">No party obligations were identified in this document.</p>
      ) : (
        <div className="ws-obligations">
          {categories.map((category) => (
            <ObligationCategoryRow
              key={category.key}
              title={category.title}
              items={category.items}
              open={category.key === openKey}
              expanded={expanded}
              onToggle={() => {
                setExpanded(false);
                setOpen(category.key === openKey ? "" : category.key);
              }}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function ObligationCategoryRow({
  title, items, open, expanded, onToggle,
}: {
  title: string;
  items: ObligationItem[];
  open: boolean;
  expanded: boolean;
  onToggle: () => void;
}) {
  const { point, target } = useHighlight();
  const panelId = useId();
  const shown = expanded ? items : items.slice(0, OBLIGATIONS_SHOWN);
  return (
    <div className="ws-obligations__group" data-open={open ? "true" : "false"}>
      <button
        type="button"
        className="ws-obligations__party"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={onToggle}
      >
        <span className="ws-obligations__partyname">{title}</span>
        <span className="ws-obligations__count">{items.length}</span>
        <span className="ws-obligations__chev" aria-hidden="true">
          {open ? <IconChevronUp size={14} /> : <IconChevronDown size={14} />}
        </span>
      </button>
      <ul className="ws-obligations__list" id={panelId} hidden={!open}>
        {shown.map((item) => (
          <li key={item.id} className="ws-obligations__item">
            <span className="ws-status ws-status--match" aria-hidden="true">
              <IconCheckCircle size={14} />
            </span>
            {item.evidence_id ? (
              <button
                type="button"
                className="ws-obligations__jump"
                aria-current={target === item.evidence_id ? "true" : undefined}
                title={sectionRef(item.section_ref)
                ? `Show ${sectionRef(item.section_ref)} in the document`
                : "Show in the document"}
                onClick={() => point(item.evidence_id!, "the cited")}
              >
                {item.obligation_text}
              </button>
            ) : (
              <span className="ws-obligations__text">{item.obligation_text}</span>
            )}
          </li>
        ))}
        {!expanded && items.length > OBLIGATIONS_SHOWN ? (
          <li className="ws-pane__note">+{items.length - OBLIGATIONS_SHOWN} more</li>
        ) : null}
      </ul>
    </div>
  );
}
