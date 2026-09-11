/**
 * PostCSS — added 2026-09-11 for Tailwind v4, and deliberately the ONLY global
 * change this stage makes.
 *
 * Tailwind is scoped to the Ask route by `src/app/dashboard/ask/ai.css`, which
 * imports `theme.css` and `utilities.css` and NEVER `preflight.css`. Nothing here
 * resets an element, and no utility can match existing markup: every utility is
 * emitted under the `tw:` namespace (see that file's header).
 *
 * This file is global because PostCSS is, which is exactly why the stage is gated
 * on a byte-identical diff of the previously-emitted CSS chunks — adding a
 * PostCSS pipeline could in principle re-minify sheets that contain no Tailwind
 * at all. `docs/design/TAILWIND_ISOLATION.md` records the measurement.
 */
const config = {
  plugins: { "@tailwindcss/postcss": {} },
};

export default config;
