// React's own rules of hooks, enforced (strict review, 2026-10-13: none ran before,
// and a ref written during render reached a commit). Scoped to the React rules —
// formatting and style stay with the existing tsc + forbidden-terms lint.
import tsParser from "@typescript-eslint/parser";
import reactHooks from "eslint-plugin-react-hooks";

export default [
  { ignores: [".next*/**", "node_modules/**", "e2e/**", "scripts/**"] },
  {
    files: ["src/**/*.{ts,tsx}"],
    languageOptions: { parser: tsParser, parserOptions: { ecmaFeatures: { jsx: true } } },
    plugins: { "react-hooks": reactHooks },
    rules: reactHooks.configs.recommended.rules,
  },
];
