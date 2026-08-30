/**
 * A region that is planned but not yet built in this phase — said plainly, with
 * no clickable path anywhere else (owner directive, 2026-08-30 cleanup: the new
 * UI must carry no navigation into the legacy application, and a placeholder is
 * not licence to link around that rule). The capability itself is not gone — the
 * backend and the existing verification screens still work — it simply is not
 * reachable by a click from here yet.
 *
 * Distinct from `DomainPlaceholder`, which is for capabilities the BACKEND does
 * not offer yet; this is for UI the roadmap sequences later.
 */

export function NextSlice({ title, note }: { title: string; note?: string }) {
  return (
    <>
      <div className="ws-pane__head">
        <h2 className="ws-pane__title">{title}</h2>
      </div>
      <div className="ws-state ws-state--next" role="note" aria-label={`${title} — not in this build yet`}>
        <p>This pane arrives in a later build slice.</p>
        {note ? <p className="ws-pane__note">{note}</p> : null}
      </div>
    </>
  );
}
