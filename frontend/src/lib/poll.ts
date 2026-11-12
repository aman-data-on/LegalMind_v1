/** Run `run` every `ms` while the tab is visible, and once more when it is shown again —
 *  a hidden tab asks the server nothing. Returns the stop function (an effect's cleanup). */
export function pollWhileVisible(run: () => void, ms: number): () => void {
  const tick = () => { if (!document.hidden) run(); };
  const timer = setInterval(tick, ms);
  document.addEventListener("visibilitychange", tick);
  return () => { clearInterval(timer); document.removeEventListener("visibilitychange", tick); };
}
