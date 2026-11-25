// Its own module so the root Toaster and the sign-in page do not load all of labels.ts (W2-2).
/** The shared states and components' own words (UX Batch 2; PLAIN-LANGUAGE.md §2.6, §5):
 *  an error says what failed and the fix, never an apology; a button is a verb. */
export const FEEDBACK_COPY = {
  retry: "Try again",
  dismiss: "Dismiss",
  defaultFix: "Check your connection and try again. If it keeps failing, tell your administrator.",
  reference: (id: string) => `Error reference for support: ${id}`,
  loading: "Loading…",
  chooseFile: "Choose file",
  chooseAnother: "Choose another file",
  dropTitle: "Drag and drop your file here",
  dropOr: "or choose one from your computer",
  fileHint: "PDF, Word, Markdown or text, up to 25 MB",
  preview: "Preview",
  preparingPreview: "Preparing preview…",
  previewFailed: "The preview could not be shown",
  downloadPdf: "Download PDF",
  downloadWord: "Download Word",
  openPdf: "Open the PDF in a new tab",
  noInlinePdf: "This browser can’t show the PDF here",
  noInlinePdfFix: "Open it in a new tab, or download it below. It is the same file.",
  close: "Close",
} as const;
