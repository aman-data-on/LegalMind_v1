import { useEffect } from "react";

/** The faces a first screen draws, started while the page's data still loads: a face fetched only
 *  when text first uses it swaps in after layout and reflows it (phone CLS, 2026-11-06). W2-5:
 *  every page draws Plex Sans (one file, 400/500/600) — the shell starts it; the serif and mono
 *  belong to the components that draw a document (the contract workspace, a template, the new-
 *  contract preview), so each of those starts them itself — keyed on the component, not the URL. */
export const SANS_FACES = ['400 1em "IBM Plex Sans"', '500 1em "IBM Plex Sans"', '600 1em "IBM Plex Sans"'];
export const DOCUMENT_FACES = [
  '400 1em "Source Serif 4"', '700 1em "Source Serif 4"', 'italic 400 1em "Source Serif 4"', '400 1em "IBM Plex Mono"',
];

export function useStartFaces(faces: readonly string[]): void {
  useEffect(() => {
    for (const face of faces) void document.fonts?.load(face).catch(() => undefined);
  }, [faces]);
}
