"use client";

/**
 * Diff-Talk (owner, 2026-10-12/13) — our document beside a client contract, clause
 * by clause. SETUP until both documents are chosen, then REVIEW. The two sides
 * live in the URL — the one source of truth, so a comparison is a link and Back
 * undoes a step.
 */

import { useCallback, useEffect, useState } from "react";

import { PageHeader } from "@/components/page/PageHeader";
import { api, describeError } from "@/lib/api";
import type { Contract, WebsiteDocument } from "@/lib/types";
import { Review } from "./Review";
import { Setup } from "./Setup";

/** Every document the reader may pick, not just the first page.
 *  ponytail: capped at 2,000 in a native select; add a search box beyond that. */
async function allDocuments(): Promise<Contract[]> {
  const out: Contract[] = [];
  for (let page = 1; page <= 20; page++) {
    const { items, pagination } = await api.contracts(page, 100);
    out.push(...items);
    if (!items.length || out.length >= pagination.total) break;
  }
  return out.filter((c) => c.latest_version?.id);
}

const loadLists = () => Promise.all([api.websiteDocuments(), allDocuments()]);

export function DiffTalkPage({ left, right, onChange }: {
  left: string;
  right: string;
  onChange: (left: string, right: string) => void;
}) {
  const [website, setWebsite] = useState<WebsiteDocument[]>([]);
  const [documents, setDocuments] = useState<Contract[]>([]);
  const [listError, setListError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const [w, d] = await loadLists();
    setWebsite(w);
    setDocuments(d);
  }, []);

  useEffect(() => {
    let cancelled = false;
    loadLists()
      .then(([w, d]) => { if (!cancelled) { setWebsite(w); setDocuments(d); } })
      .catch((e: unknown) => { if (!cancelled) setListError(describeError(e)); });
    return () => { cancelled = true; };
  }, []);

  // The house page header; a review takes the full width the two texts need (as a
  // contract or a template does), choosing sits in the page width like every list.
  if (left && right) {
    return (
      <>
        <PageHeader wide title="Diff-Talk" />
        <Review key={`${left}|${right}`} left={left} right={right}
                onChange={(side) => (side === "left" ? onChange("", right) : onChange(left, ""))} />
      </>
    );
  }
  return (
    <div className="lm-page">
      <PageHeader title="Diff-Talk"
                  meta={<span>Compare our document with a client contract, clause by clause. Colours mark wording changes, not whether they are acceptable.</span>} />
      <Setup left={left} right={right} website={website} documents={documents}
             listError={listError} onChange={onChange}
             onUploaded={async (side, ref) => {
               await refresh().catch(() => undefined);
               if (ref) onChange(side === "left" ? ref : left, side === "right" ? ref : right);
             }} />
    </div>
  );
}
