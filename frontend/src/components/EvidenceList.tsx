/**
 * Evidence with its document location — locked 52.6 ("Evidence viewer with
 * document location"), Steps 32, 34.13, 42.20, and rule 11.
 *
 * Every Finding traces to the source text it was built from. The location fields
 * are shown because "the liability clause says six months" is not evidence — "page
 * 14, clause 11.2 says six months" is.
 *
 * An empty list is a legitimate state, not an error: a MISSING established by
 * absence carries no evidence (45C.15, N-34, 49.7 r3). It is labelled as absence
 * rather than rendered as a gap.
 */

import type { Evidence } from "@/lib/types";

export function EvidenceList({ evidence }: { evidence: Evidence[] }) {
  if (evidence.length === 0) {
    return (
      <p className="evidence--none">
        No supporting text was found in the document for this Requirement.
      </p>
    );
  }

  return (
    <details className="evidence">
      <summary>
        Evidence ({evidence.length} {evidence.length === 1 ? "extract" : "extracts"})
      </summary>
      <ul>
        {evidence.map((item) => (
          <li key={item.id} className="evidence__item">
            <p className="evidence__location">
              {formatLocation(item)}
              {/* 34.8 — OCR-derived text is labelled, so its provenance is visible. */}
              {item.source_type === "OCR" ? (
                <span className="evidence__ocr" title="Text recovered by OCR">
                  {" "}
                  · OCR
                </span>
              ) : null}
              <span className="evidence__relationship"> · {item.relationship_type}</span>
            </p>
            <blockquote className="evidence__text">{item.content}</blockquote>
          </li>
        ))}
      </ul>
    </details>
  );
}

export function formatLocation(item: Evidence): string {
  const parts: string[] = [];
  if (item.section_number) parts.push(`Clause ${item.section_number}`);
  if (item.section_title) parts.push(item.section_title);
  if (item.page_number !== null) parts.push(`page ${item.page_number}`);
  return parts.length > 0 ? parts.join(" · ") : "Location not recorded";
}
