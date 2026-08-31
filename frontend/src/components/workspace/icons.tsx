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
