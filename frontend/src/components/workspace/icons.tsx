/**
 * Inline SVG icons for the workspace — the 2026-09-01 reference-matched restyle.
 * All decorative by default (aria-hidden; the accessible name lives on the
 * control that uses one). Stroke inherits currentColor so the status hues come
 * from the token the parent already carries. No emoji anywhere (house rule).
 */

const S = {
  width: 16,
  height: 16,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
};

export function IconCheckCircle({ size = 16 }: { size?: number }) {
  return (
    <svg {...S} width={size} height={size}>
      <circle cx="12" cy="12" r="10" />
      <path d="m8.5 12.5 2.5 2.5 4.5-5.5" />
    </svg>
  );
}

export function IconAlertCircle({ size = 16 }: { size?: number }) {
  return (
    <svg {...S} width={size} height={size}>
      <circle cx="12" cy="12" r="10" />
      <path d="M12 7v6" />
      <path d="M12 16.6v.2" />
    </svg>
  );
}

export function IconXCircle({ size = 16 }: { size?: number }) {
  return (
    <svg {...S} width={size} height={size}>
      <circle cx="12" cy="12" r="10" />
      <path d="m9 9 6 6M15 9l-6 6" />
    </svg>
  );
}

export function IconSearch({ size = 16 }: { size?: number }) {
  return (
    <svg {...S} width={size} height={size}>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.8-3.8" />
    </svg>
  );
}

export function IconChevronUp({ size = 16 }: { size?: number }) {
  return (
    <svg {...S} width={size} height={size}>
      <path d="m6 14 6-6 6 6" />
    </svg>
  );
}

export function IconChevronDown({ size = 16 }: { size?: number }) {
  return (
    <svg {...S} width={size} height={size}>
      <path d="m6 10 6 6 6-6" />
    </svg>
  );
}

export function IconMaximize({ size = 16 }: { size?: number }) {
  return (
    <svg {...S} width={size} height={size}>
      <path d="M8 3H3v5M16 3h5v5M8 21H3v-5M16 21h5v-5" />
    </svg>
  );
}

export function IconRefresh({ size = 16 }: { size?: number }) {
  return (
    <svg {...S} width={size} height={size}>
      <path d="M21 12a9 9 0 1 1-2.64-6.36" />
      <path d="M21 3v6h-6" />
    </svg>
  );
}

export function IconDownload({ size = 16 }: { size?: number }) {
  return (
    <svg {...S} width={size} height={size}>
      <path d="M12 3v12" />
      <path d="m7 10 5 5 5-5" />
      <path d="M4 21h16" />
    </svg>
  );
}

export function IconLink({ size = 16 }: { size?: number }) {
  return (
    <svg {...S} width={size} height={size}>
      <path d="M10 14a5 5 0 0 0 7.07 0l3-3a5 5 0 0 0-7.07-7.07l-1.5 1.5" />
      <path d="M14 10a5 5 0 0 0-7.07 0l-3 3a5 5 0 0 0 7.07 7.07l1.5-1.5" />
    </svg>
  );
}

export function IconArrowLeft({ size = 16 }: { size?: number }) {
  return (
    <svg {...S} width={size} height={size}>
      <path d="M19 12H5" />
      <path d="m11 18-6-6 6-6" />
    </svg>
  );
}

export function IconSparkle({ size = 16 }: { size?: number }) {
  return (
    <svg {...S} width={size} height={size}>
      <path d="M12 3v0c.6 3.9 3.5 6.8 7.4 7.4v0-0C15.5 11 12.6 13.9 12 17.8v0-0C11.4 13.9 8.5 11 4.6 10.4v0-0C8.5 9.8 11.4 6.9 12 3Z" />
      <path d="M19 16.5c.25 1.6 1.4 2.75 3 3-1.6.25-2.75 1.4-3 3-.25-1.6-1.4-2.75-3-3 1.6-.25 2.75-1.4 3-3Z" />
    </svg>
  );
}

export function IconSend({ size = 16 }: { size?: number }) {
  return (
    <svg {...S} width={size} height={size}>
      <path d="m3 11 18-8-8 18-2.5-7.5L3 11Z" />
    </svg>
  );
}

export function IconHistory({ size = 16 }: { size?: number }) {
  return (
    <svg {...S} width={size} height={size}>
      <path d="M4 4h16v12H8l-4 4V4Z" />
    </svg>
  );
}

export function IconFile({ size = 16 }: { size?: number }) {
  return (
    <svg {...S} width={size} height={size}>
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8Z" />
      <path d="M14 3v5h5" />
    </svg>
  );
}

export function IconClock({ size = 16 }: { size?: number }) {
  return (
    <svg {...S} width={size} height={size}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3.5 2" />
    </svg>
  );
}

export function IconChevronRight({ size = 16 }: { size?: number }) {
  return (
    <svg {...S} width={size} height={size}>
      <path d="m9 6 6 6-6 6" />
    </svg>
  );
}

export function IconUploadCloud({ size = 16 }: { size?: number }) {
  return (
    <svg {...S} width={size} height={size}>
      <path d="M7 18a4.5 4.5 0 0 1-1-8.9A5 5 0 0 1 16 8h.5a3.5 3.5 0 0 1 .5 7" />
      <path d="M12 12v9" />
      <path d="m9 15 3-3 3 3" />
    </svg>
  );
}

/* ---------------------------------------------------------------------------
 * Pipeline strip (2026-09-01, owner-supplied Documents reference).
 * The reference used unicode glyphs (▤ ◎ ▥ ◇ 🔒 →); these are their SVG
 * equivalents, because this file's rule is no emoji and a glyph's weight and
 * baseline vary per platform font in a row where five marks must look equal.
 * ------------------------------------------------------------------------- */

/** Extraction — a page whose lines are being read, not interpreted. */
export function IconScanText({ size = 16 }: { size?: number }) {
  return (
    <svg {...S} width={size} height={size}>
      <path d="M3 7V5a2 2 0 0 1 2-2h2" />
      <path d="M17 3h2a2 2 0 0 1 2 2v2" />
      <path d="M21 17v2a2 2 0 0 1-2 2h-2" />
      <path d="M7 21H5a2 2 0 0 1-2-2v-2" />
      <path d="M7 9h10" />
      <path d="M7 13h7" />
      <path d="M7 17h4" />
    </svg>
  );
}

/** The declared Document Type — a label the human attaches, hence a tag. */
export function IconTag({ size = 16 }: { size?: number }) {
  return (
    <svg {...S} width={size} height={size}>
      <path d="M12.6 2.7a2 2 0 0 0-1.4-.6H4a2 2 0 0 0-2 2v7.2a2 2 0 0 0 .6 1.4l8 8a2 2 0 0 0 2.8 0l6.8-6.8a2 2 0 0 0 0-2.8Z" />
      <path d="M7 7h.01" />
    </svg>
  );
}

/** Evaluation against a Company Standard — a balance, because that is
 *  literally what a NUMERIC_COMPARISON evaluator does: it weighs one stated
 *  value against another. Not a brain and not a spark. */
export function IconScale({ size = 16 }: { size?: number }) {
  return (
    <svg {...S} width={size} height={size}>
      <path d="M12 3v18" />
      <path d="M7 21h10" />
      <path d="M5 7h14" />
      <path d="m5 7-3 6h6Z" />
      <path d="m19 7-3 6h6Z" />
    </svg>
  );
}

/** A Finding that traces to its evidence — a document with a check, never a
 *  score dial or a gauge (rule 12: no generic risk score). */
export function IconFileCheck({ size = 16 }: { size?: number }) {
  return (
    <svg {...S} width={size} height={size}>
      <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" />
      <path d="M14 2v5h6" />
      <path d="m9 15 2 2 4-4" />
    </svg>
  );
}

export function IconLock({ size = 16 }: { size?: number }) {
  return (
    <svg {...S} width={size} height={size}>
      <rect x="3" y="11" width="18" height="11" rx="2" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
  );
}

export function IconArrowRight({ size = 16 }: { size?: number }) {
  return (
    <svg {...S} width={size} height={size}>
      <path d="M5 12h14" />
      <path d="m13 6 6 6-6 6" />
    </svg>
  );
}

export function IconExternal({ size = 16 }: { size?: number }) {
  return (
    <svg {...S} width={size} height={size}>
      <path d="M15 3h6v6" />
      <path d="M10 14 21 3" />
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
    </svg>
  );
}

export function IconX({ size = 16 }: { size?: number }) {
  return (
    <svg {...S} width={size} height={size}>
      <path d="M18 6 6 18M6 6l12 12" />
    </svg>
  );
}
