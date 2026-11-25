/** The tab-only panes' scripts (W2-3), started on intent — a tab hovered, focused or touched,
 *  the ⋯ menu opened — so the first open rarely waits for them (W2 r2). Each import runs once. */
export const loadChanges = () => import("./ChangesPane");
export const loadCompare = () => import("./VersionComparison");
export const loadReport = () => import("./ReviewReportPage");

export function preloadView(view: string): void {
  if (view === "changes") void loadChanges();
  else if (view === "report") void loadReport();
}

/** Props for a tab: start its pane's script on the first sign of intent. */
export const preloadProps = (view: string) => ({
  onPointerEnter: () => preloadView(view), onFocus: () => preloadView(view), onTouchStart: () => preloadView(view),
});
