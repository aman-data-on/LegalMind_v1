# Tailwind isolation — the measurement

**Status: 📁 record of a measurement. Decides nothing on its own; the decision is DD-20.**
Taken 2026-09-11, on `origin/main` at `e0bb565`.

## Why this document exists

The owner approved Tailwind for the Ask surface on one condition: **existing screens untouched**.
That is a claim about bytes, not a feeling about markup, so it was measured before the change was
committed — and this file is the method, so the next person can repeat it rather than trust it.

A green design-QA run is **not** the proof. Its threshold is `maxDiffPixelRatio: 0.001` — 1152px of
a 1280×900 shot — and three baselines drifted under that threshold and passed green for weeks
(2026-09-11; see `e2e/visual.spec.ts`'s ⚠️ block). Only the emitted CSS settles it.

## Method

Two production builds of the same tree, into separate dist directories, with the Turbopack cache
cleared between them (it will otherwise serve a stale chunk — observed during this measurement,
and it briefly made a removed probe look like it was still shipping):

```bash
cd frontend
rm -rf node_modules/.cache .next-before
LEGALMIND_NEXT_DIST=.next-before npx next build        # BEFORE
#   … add tailwind + postcss.config.mjs + src/app/dashboard/ask/ai.css …
rm -rf node_modules/.cache .next-after
LEGALMIND_NEXT_DIST=.next-after npx next build         # AFTER
md5sum $(find .next-before -name '*.css' | sort)
md5sum $(find .next-after  -name '*.css' | sort)
```

`LEGALMIND_NEXT_DIST` is mandatory and the directory must be **relative** — Next rejects an absolute
`distDir` outside the project (it exits 1 after an apparently successful build, which is confusing
the first time). A bare `next build` is refused outright by `next.config.ts`'s guard, because it
would overwrite the `.next` the live service is serving.

Clean up afterwards: the temporary dist directories make Next rewrite `tsconfig.json` and
`next-env.d.ts`, and those edits are measurement artifacts, not part of the change.

## Result

| Chunk | BEFORE | AFTER |
|---|---|---|
| `0qle5ap9q-rbo.css` | `56a3ad601614411a998e3f69a1f912ea` | **identical** |
| `2o1stnin98j-x.css` | `f2ce9567a508f46d4b2701bd71819732` | **identical** |
| `3u5kspdyzs47t.css` | `1c0299a3a0cf73eb44e8a2defa207e5f` | **identical** |
| `06hvl17eluuvy.css` | — | new, 150 bytes |

**Every previously-emitted stylesheet is byte-identical.** This is the assertion that matters, and
it also clears the subtler risk: adding a PostCSS pipeline is global, so it could in principle
re-minify sheets containing no Tailwind at all. It did not.

The new chunk, in full, with no utility in use anywhere:

```css
@layer theme{:root,:host{--tw-text-xs:.75rem;--tw-text-sm:.875rem;--tw-text-base:1rem;
--tw-text-lg:1.125rem;--tw-text-xl:1.25rem;--tw-radius-sm:.25rem}}@layer components,utilities;
```

### Three checks on that chunk

| Check | Result |
|---|---|
| Preflight absent — `box-sizing:border-box` occurrences | **0** |
| Bare-element resets (`html`, `body`, `h1`, `p`, `ul`, `button`, `table`) | **0** |
| Unprefixed utility selectors that could match existing markup | **0** |

And utilities genuinely work: a temporary `tw:isolate` probe emitted
`.tw\:isolate{isolation:isolate}` and grew the chunk to 220 bytes. The probe was removed before
commit — shipping a decorative class to prove a point is not a reason to ship a class.

## What this does NOT claim

It touches `:root`. Six custom properties (`--tw-text-*`, `--tw-radius-sm`) are declared on
`:root,:host` by Tailwind's theme layer. They are `--tw-*` namespaced, so they cannot collide with
any `--ws-*` token, and they paint nothing on their own — but "zero global effect" would be false
and this file will not say it.

## The constraint to know before using a utility

**Cascade layers outrank specificity.** A rule in any `@layer` loses to an unlayered rule, whatever
the selectors say. `workspace.css` is unlayered, so `.ws a` (`workspace.css:171`) beats
`tw:text-blue-500` every time, silently — which is a sharper version of the bug that already cost
this repo a day, when `.ws a` at (0,1,1) beat a bare class at (0,1,0) and rendered "New chat"
blue-on-blue.

So Tailwind utilities here are for **new markup no `.ws` rule already targets**. They are not a
route to restyling anything the design system owns; use the `--ws-*` tokens for that.

## Merge condition

If the diff touches `globals.css`, `workspace.css`, or any `*.png` under
`e2e/visual.spec.ts-snapshots/`, isolation was not achieved — abandon the branch rather than patch
it. The change is additive files only, so rollback is a single `git revert` plus `npm ci`.
