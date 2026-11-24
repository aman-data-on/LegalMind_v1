import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import { contractHref, contractTabFromPath, phoneView, shortDate } from "@/components/workspace/model";
import { BRIEF_COPY, LAWYER_COPY, MENU_COPY } from "@/lib/labels";
import { leadNote, noteHeading } from "@/components/workspace/WorkspaceHeader";
import type { SentNote } from "@/lib/types";
import { hasTypedText, rememberInitial } from "@/components/Dialog";

const css = (p: string) => readFileSync(p, "utf8");

describe("U2 workspace layout (AB-225)", () => {
  it("UI-13: the report is an address of its own, and the menu names each file by its type", () => {
    expect(contractTabFromPath("/contracts/abc/report")).toEqual({ tab: "report" });
    expect(contractHref("abc", "report")).toBe("/contracts/abc/report");
    expect(MENU_COPY.download(2, "application/pdf", false)).toBe("Download version 2 (PDF)");
    expect(MENU_COPY.download(3, "application/vnd.openxmlformats-officedocument.wordprocessingml.document", true))
      .toBe("Download draft version 3 (Word)");
    expect([MENU_COPY.compare, MENU_COPY.compareTemplate]).toEqual(["Compare two versions", "Compare with our template"]);
  });
  it("UI-35 / AM-473: 'and N more' points at the Changes tab; a taken-back note says when", () => {
    expect(BRIEF_COPY.asksMoreLink(7)).toBe("and 7 more on the Changes tab");
    expect(BRIEF_COPY.yourNoteTaken("24 Nov 2026")).toBe("Your note to Legal (taken back 24 Nov 2026)");
  });
  it("UI-07: no standard is said once, in plain words (no 'measure')", () => {
    expect(LAWYER_COPY.standardSilent).toBe("No standard covers this clause. Decide from the wording.");
    expect(css("src/lib/changes.ts")).not.toMatch(/could not measure/);
    // the answer tray sticks to the foot of the card, on a phone above the tab bar
    expect(css("src/components/workspace/changes.css")).toMatch(/\.cx-card \.cx-compose \{ position: sticky; bottom:/);
  });
  it("UI-06 / UI-04: the page padding is tokens; the brief row is reserved before it loads", () => {
    const ws = css("src/app/dashboard/workspace.css");
    expect(ws).not.toMatch(/\.ws-page \{[^}]*padding: (64|48)px/);
    expect(ws).toMatch(/@media \(max-width: 640px\) \{\n  \.ws-page \{ padding: var\(--s-4\); box-shadow: none/);
    expect(css("src/components/workspace/brief.css")).toMatch(/\.lm-brief__row \{[^}]*min-block-size: calc\(var\(--s-6\) \+ var\(--s-2\)\)/);
  });
  it("r2: a tap on the phone's bar leaves the Report view — every region and Ask live on Document", () => {
    for (const which of ["document", "summary", "points", "ask"]) expect(phoneView(which)).toBe("document");
    expect(phoneView("changes")).toBe("changes");
    const page = css("src/components/workspace/WorkspacePage.tsx");
    // never "only from Changes": the check is against the view the tap needs
    expect(page).toMatch(/const next = phoneView\(which\);\n\s+if \(view !== next\) chooseView\(next\);/);
    expect(page).toMatch(/if \(view !== phoneView\("ask"\)\) chooseView\("document"\);/);
    expect(page).not.toMatch(/if \(view === "changes"\) chooseView\("document"\)/);
  });
  it("r2: a note someone else sent is said to be theirs", () => {
    expect(BRIEF_COPY.noteFrom("Asha")).toBe("Note to Legal from Asha");
    expect(BRIEF_COPY.noteFromTaken("Asha", "24 Nov 2026")).toBe("Note to Legal from Asha (taken back 24 Nov 2026)");
  });
});

describe("U2 r3: the note the brief leads with, and whose it is", () => {
  const me = { user_id: "me", name: "Me", email: "me@x" }, asha = { user_id: "a", name: "Asha", email: "a@x" };
  const send = (note: string, by = me, taken: string | null = null): SentNote =>
    ({ to: asha, by, note, sent_at: "2026-11-20T10:00:00+00:00", taken_back_at: taken });
  it("leads with the newest send only when it had a note — the re-send picker's own source", () => {
    const older = send("First", me, "2026-11-21T10:00:00+00:00");
    expect(leadNote([send(""), older], true)).toBeNull();          // newest send had no note
    expect(leadNote([send(""), older], false)).toBeNull();
    expect(leadNote([send("Now"), older], true)?.note).toBe("Now");
    expect(leadNote([older], true)).toBeNull();                      // held again? never a taken-back note
    expect(leadNote([older], false)?.note).toBe("First");            // after a take-back it stays
  });
  it("says 'Your note' only for the reader's own; another's is named; taken back is said", () => {
    const back = "2026-11-24T09:00:00+00:00";
    expect(noteHeading(send("x"), "me")).toBe("Your note to Legal");
    expect(noteHeading(send("x", me, back), "me")).toBe(`Your note to Legal (taken back ${shortDate(back)})`);
    expect(noteHeading(send("x", asha), "me")).toBe("Note to Legal from Asha");
    expect(noteHeading(send("x", asha, back), "me")).toBe(`Note to Legal from Asha (taken back ${shortDate(back)})`);
    expect(noteHeading({ ...send("x"), by: null }, "me")).toBe("Your note to Legal");
  });
});

describe("U2 r5: Esc never throws away a typed draft", () => {
  // A controlled React field: React keeps `defaultValue` equal to `value` as the reader
  // types, so comparing the two (round 4) never saw a change. The field here behaves so.
  const controlled = (value: string) => {
    const field = { tagName: "TEXTAREA", dataset: {} as DOMStringMap, _v: value,
      get value() { return this._v; }, set value(v: string) { this._v = v; },
      get defaultValue() { return this._v; } };
    return field;
  };
  it("remembers the text the reader found, and sees every edit after it", () => {
    const field = controlled("Note from sales");
    rememberInitial(field as unknown as EventTarget);          // focus: the draft as found
    expect(hasTypedText(field as unknown as EventTarget)).toBe(false);
    field.value = "Our position: a mutual cap";                   // the lawyer replaces it
    expect(field.defaultValue).toBe(field.value);                 // what fooled round 4
    expect(hasTypedText(field as unknown as EventTarget)).toBe(true);   // Esc keeps it
    rememberInitial(field as unknown as EventTarget);          // focus again: still the first text
    expect(hasTypedText(field as unknown as EventTarget)).toBe(true);
    field.value = "Note from sales";                              // put back as found
    expect(hasTypedText(field as unknown as EventTarget)).toBe(false);
  });
  it("is never fooled by a field it never saw focused, or by something that is not a field", () => {
    expect(hasTypedText(controlled("x") as unknown as EventTarget)).toBe(false);
    expect(hasTypedText({ tagName: "BUTTON", dataset: {} } as unknown as EventTarget)).toBe(false);
    expect(hasTypedText(null)).toBe(false);
  });
});
