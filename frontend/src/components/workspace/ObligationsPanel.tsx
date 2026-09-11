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
 * Each group shows its first five items and a "Show N more" control OF ITS
 * OWN (owner, 2026-09-10). The previous "+1 more" was a non-interactive line
 * and the only way to expand it was a "View all" button up in the section
 * header, which reset on every accordion click — so a group headed "6" could
 * never be made to show six. The count and the rendered items now always
 * reconcile: 5 + "Show 1 more", or all 6 + "Show less".
 *
 * Flow: read what exists; when nothing was extracted yet, request the
 * extraction once (the server runs it synchronously — the Ask precedent) and
 * read again. Every failure is an honest quiet sentence — obligations are a
 * convenience, and their absence blocks nothing.
 */

import { useEffect, useId, useState } from "react";
import { sectionRef } from "@/lib/documentTypes";

import { useAskIntent } from "./askIntent";

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

/** Items shown per party before its own "Show N more" expands the list. */
export const OBLIGATIONS_SHOWN = 5;

export function ObligationsPanel({ documentVersionId }: { documentVersionId: string }) {
  const [state, setState] = useState<Load>({ kind: "loading" });
  /** null = "the first category", the sensible default; "" = the user closed it. */
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setState({ kind: "loading" });
    setOpen(null);

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

  return (
    <section className="ws-analysis__section" aria-label="Key obligations">
      <div className="ws-analysis__head">
        <h3 className="ws-analysis__title">Key obligations</h3>
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
              onToggle={() => setOpen(category.key === openKey ? "" : category.key)}
            />
          ))}
        </div>
      )}
    </section>
  );
}

export function ObligationCategoryRow({
  title, items, open, onToggle,
}: {
  title: string;
  items: ObligationItem[];
  open: boolean;
  onToggle: () => void;
}) {
  const { point, target } = useHighlight();
  // Null on any surface outside the workspace (the provider lives there), and the
  // control simply is not rendered — the same degradation the Finding card uses.
  const askIntent = useAskIntent();
  const panelId = useId();
  const [expanded, setExpanded] = useState(false);
  // A closed group forgets its expansion; reopening starts at the first five.
  useEffect(() => {
    if (!open) setExpanded(false);
  }, [open]);
  const hidden = items.length - OBLIGATIONS_SHOWN;
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
                ? `Show clause ${sectionRef(item.section_ref)} in the document`
                : "Show in the document"}
                onClick={() => point(item.evidence_id!, "the cited")}
              >
                {item.obligation_text}
              </button>
            ) : (
              <span className="ws-obligations__text">{item.obligation_text}</span>
            )}
            {/* An obligation could be pointed at but not asked about, so reading one
                that raised a question was a dead end — the reader had to retype it
                into Ask. The draft is editable and nothing sends until they send it
                (the Finding handoff's own rule). No finding id: an obligation is a
                descriptive fact about the document's text, not a Finding. */}
            {askIntent ? (
              <button
                type="button"
                className="ws-obligations__ask"
                onClick={() => askIntent.ask(
                  `What does this document say about "${item.obligation_text.slice(0, 120)}"?`)}
              >
                Ask about this
              </button>
            ) : null}
          </li>
        ))}
        {hidden > 0 ? (
          <li>
            <button
              type="button"
              className="ws-obligations__more"
              aria-expanded={expanded}
              onClick={() => setExpanded((v) => !v)}
            >
              {expanded ? "Show less" : `Show ${hidden} more`}
            </button>
          </li>
        ) : null}
      </ul>
    </div>
  );
}
