import { defineConfig } from "vitest/config";

/**
 * Vitest is the locked frontend test runner (Step 39). Nothing else is added:
 * components are asserted by rendering them to static markup with
 * `react-dom/server`, which ships with React, rather than by introducing a DOM
 * testing library and jsdom. Browser-level workflow testing is Playwright's job
 * (Step 39, Step 54) and belongs to the CI unit, not here.
 */
export default defineConfig({
  esbuild: { jsx: "automatic" },
  test: {
    include: ["src/__tests__/**/*.test.ts", "src/__tests__/**/*.test.tsx"],
    environment: "node",
  },
  resolve: {
    alias: { "@": new URL("./src", import.meta.url).pathname },
  },
});
