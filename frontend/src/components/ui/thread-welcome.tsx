/** Ask's empty-chat heading, shared by the Thread and the shell's start-up skeleton (W2-4), so
 *  the prerendered heading and the real one are the same element: same classes, same words. */
export const WELCOME_CLASS = "text-foreground text-center font-semibold tracking-tight";

/** The skeleton's copy, in the Ask page's own grid and the Thread's centring column. A chat link (`?id=`) must not show it:
 *  the inline script marks <html> before first paint and a CSS rule hides the heading (the
 *  prerendered HTML cannot read the query; an attribute on the heading itself did not survive
 *  every render). No data, one line, no CSP on this app (ops/production/README.md). */
export function WelcomeSkeleton({ title }: { title: string }) {
  // W2 r2: the real page's geometry — the rail's cell, the conversation column, the heading,
  // and an empty block the height of the composer and openers below it — so the heading's box
  // is the real one's and nothing moves when the page replaces it
  return (
    <div className="ws-chat">
      <div className="ws-chat__rail lm-askskel__rail" aria-hidden="true" />
      <div className="ws-chat__main">
        <div className="lm-askskel mx-auto flex w-full max-w-2xl flex-1 flex-col justify-center px-4 pt-6">
          <script dangerouslySetInnerHTML={{ __html: "if(/[?&]id=/.test(location.search))document.documentElement.setAttribute('data-ask-chat','')" }} />
          <h2 data-slot="aui_thread-welcome" className={WELCOME_CLASS}>{title}</h2>
          <div className="lm-askskel__foot" aria-hidden="true" />
        </div>
      </div>
    </div>
  );
}
