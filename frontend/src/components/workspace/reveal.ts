/** Bring an error or a form shown at the end of the conversation into view once, when
 *  it appears: on phones it sat under the sticky question box (Ask audit H4,
 *  2026-10-29). It is always the last thing in the conversation, so the conversation is
 *  scrolled to its end, as for a new answer: the question box then sits below it and the
 *  jump arrow hides. One frame later, so the form is laid out. Pass it as a ref; it is a
 *  module constant, so a re-render never scrolls again. */
export function reveal(el: HTMLElement | null) {
  if (!el) return;
  requestAnimationFrame(() => {
    const viewport = el.closest<HTMLElement>("[data-slot='aui_thread-viewport']");
    if (viewport) viewport.scrollTo({ top: viewport.scrollHeight });
    else el.scrollIntoView({ block: "nearest" });
  });
}
