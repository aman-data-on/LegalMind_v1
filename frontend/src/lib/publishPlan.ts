/**
 * What a publish will actually do, worked out from the Requirement list.
 *
 * WHY THIS EXISTS. Publishing used to be one text field: "Requirement codes to
 * activate (comma separated)". Activating the AB-20 batch meant pasting 33 codes
 * into it, with nothing on screen saying which Requirements were waiting, which
 * were already active, or which would be refused — and a single typo produced
 * `unknown Requirement code: …` after the fact. The screen holds every Requirement
 * with its status already, so all of that is a group-by rather than a new endpoint.
 *
 * The logic lives here, not in the component, because `vitest.config.ts` is
 * `environment: "node"`: a count or a button label that quietly says the wrong
 * thing is exactly what a test should catch, and it can only catch it here.
 *
 * NOTHING HERE DECIDES ANYTHING. It mirrors what
 * `POST /configuration/publish` will do (`api/routers/configuration.py`) so the
 * screen can say it in advance. The server remains the only authority, and every
 * refusal below is one it already performs.
 */

import type { Requirement } from "@/lib/types";

/** Step 29's configuration lifecycle — `domain/enums.py` `ConfigStatus`. */
export const DRAFT = "DRAFT";
export const ACTIVE = "ACTIVE";
export const DEPRECATED = "DEPRECATED";

export interface PublishPlan {
  /** DRAFT Requirements, which publishing would activate. */
  drafts: Requirement[];
  /** Already ACTIVE — pinned into the snapshot whether or not anything is ticked. */
  active: Requirement[];
  /** DEPRECATED — the server refuses to publish these (AM-65). */
  retired: Requirement[];
  /** Codes that are selectable: a DRAFT that has at least one version. */
  selectable: string[];
  /**
   * DRAFT Requirements with no version at all. Activating one makes it ACTIVE, and
   * the publish then fails on `<code>: no version` — refusing the WHOLE snapshot,
   * not just that Requirement. So they are listed and disabled rather than hidden.
   */
  versionless: Requirement[];
  /** How many Requirements the resulting snapshot would pin. */
  willPin: number;
  /** The submit button's words, so it says what is about to happen. */
  action: string;
  /** A reason the button is disabled, or null. */
  blocked: string | null;
}

export function publishPlan(
  requirements: readonly Requirement[] | null,
  selected: readonly string[],
): PublishPlan {
  const all = requirements ?? [];
  const drafts = all.filter((r) => r.status === DRAFT);
  const active = all.filter((r) => r.status === ACTIVE);
  const retired = all.filter((r) => r.status === DEPRECATED);
  const versionless = drafts.filter((r) => r.versions.length === 0);
  const versionlessCodes = new Set(versionless.map((r) => r.code));
  const selectable = drafts.filter((r) => !versionlessCodes.has(r.code)).map((r) => r.code);

  // Only a selection that is actually selectable counts — a code left ticked after
  // the list reloaded must not silently widen what gets published.
  const ticked = selected.filter((code) => selectable.includes(code));
  const willPin = active.length + ticked.length;

  const pinned = `${willPin} Requirement${willPin === 1 ? "" : "s"}`;
  const action =
    ticked.length === 0
      ? `Publish ${pinned}`
      : `Activate ${ticked.length} and publish ${pinned}`;

  // "no Requirement is ACTIVE" is the server's own refusal; saying it here turns a
  // failed request into a disabled button with the reason on it.
  const blocked = willPin === 0
    ? "Nothing would be published: no Requirement is active, and none is selected."
    : null;

  return { drafts, active, retired, selectable, versionless, willPin, action, blocked };
}
