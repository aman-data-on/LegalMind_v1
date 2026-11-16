"use client";

/**
 * The PDF's own pages, drawn with pdfjs-dist (`AM-278`) from the very Blob that is
 * downloaded — so the preview shows the file on every browser, including those with no
 * built-in PDF viewer (Android Chrome, headless). Presentation only.
 */

import { useEffect, useRef, useState } from "react";

import { ErrorState } from "@/components/Feedback";
import { FEEDBACK_COPY } from "@/lib/labels";

export function PdfPages({ blob, label }: { blob: Blob; label: string }) {
  const box = useRef<HTMLDivElement | null>(null);
  const [error, setError] = useState<unknown>(null);
  useEffect(() => {
    let live = true;
    const host = box.current;
    (async () => {
      const pdfjs = await import("pdfjs-dist");
      pdfjs.GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();
      const task = pdfjs.getDocument({ data: new Uint8Array(await blob.arrayBuffer()) });
      const doc = await task.promise;
      const width = host?.clientWidth || 800;
      const ratio = window.devicePixelRatio || 1;
      for (let n = 1; n <= doc.numPages && live && host; n += 1) {
        const page = await doc.getPage(n);
        const viewport = page.getViewport({ scale: (width / page.getViewport({ scale: 1 }).width) * ratio });
        const canvas = document.createElement("canvas");
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        canvas.className = "lm-pdfpages__page";
        canvas.setAttribute("aria-label", `Page ${n} of ${doc.numPages}`);
        canvas.setAttribute("role", "img");
        host.appendChild(canvas);
        await page.render({ canvas, viewport }).promise;
      }
      await task.destroy();
    })().catch((cause: unknown) => { if (live) setError(cause); });
    return () => { live = false; host?.replaceChildren(); };
  }, [blob]);
  if (error) return <ErrorState title={FEEDBACK_COPY.previewFailed} error={error} />;
  return <div ref={box} className="lm-pdfpages" role="document" aria-label={label} tabIndex={0} />;
}
