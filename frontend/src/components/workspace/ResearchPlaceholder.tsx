/**
 * Research — the ONE disclosed placeholder screen (slice 8; PRODUCT_UX_ROADMAP
 * §E screen 10). Domain C's home when it exists: document-less statute
 * research, answering with section citations in the same grammar as Ask.
 *
 * Today it states plainly why it is empty — the statute corpus is not ratified
 * (C-16: two cited statutes were never supplied, and one owner choice between
 * the Evidence Act 1872 and the BSA 2023 is pending) — and offers NOTHING
 * interactive: no search box that would fake capability (§20), no link, no
 * button. A disclosed placeholder discloses; it does not tease.
 */

export function ResearchPlaceholder() {
  return (
    <div className="ws-state" role="note">
      <h2>Statute research isn&rsquo;t available yet.</h2>
      <p>
        This is where questions about the law itself will be asked — no uploaded document,
        answers citing statute sections, in the same cite-or-refuse grammar Ask uses.
      </p>
      <p>
        It stays empty until the statute sources are ratified into the system; that intake
        is an owner decision (registered as C-16), not a build step this screen can skip.
      </p>
    </div>
  );
}
