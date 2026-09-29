"use client";

/**
 * The Dashboard's "+ Upload Contract" action, as a centered modal (Dashboard
 * UI improvements, 2026-09-29 — item 2, "Compact Upload Experience"). Replaces
 * the inline disclosure panel that used to push the whole page down; the
 * upload flow itself (`UploadContract`) is untouched — same create → upload →
 * suggest type → analyze chain, same permissions, same validation. Only where
 * it lives, and when the network calls start, changed (the file is now shown
 * before any upload begins — see `UploadContract`'s "selected" stage).
 *
 * Reuses the shared `Dialog` shell every other Dashboard modal already uses
 * (Edit/Archive/Delete/Transfer) rather than a bespoke overlay, so focus trap,
 * Escape-to-close, scrim-click and the `.ws` token scope all come for free.
 * The one thing genuinely new to this modal — a blurred, dimmed backdrop
 * (the brief's explicit ask, distinct from the other four modals' plain dim)
 * — is opted into via `overlayClassName` rather than changed globally, so
 * Edit/Archive/Delete/Transfer keep their exact existing look.
 */

import { Dialog } from "@/components/Dialog";
import { UploadContract } from "./UploadContract";
import { IconUploadCloud, IconX } from "./icons";

export function UploadContractDialog({
  firstRun, counterparties, onClose,
}: {
  firstRun: boolean;
  counterparties?: string[] | undefined;
  onClose: () => void;
}) {
  return (
    <Dialog onClose={onClose} titleId="ws-upload-title" overlayClassName="ws-modal--blur">
      <div className="ws-upload-dialog">
        <div className="ws-upload-dialog__head">
          <span className="ws-upload-dialog__icon" aria-hidden="true"><IconUploadCloud size={22} /></span>
          <div className="ws-upload-dialog__headtext">
            <h2 id="ws-upload-title">Upload a contract</h2>
            <p className="ws-modal__body">
              Upload a contract to analyze risks, extract key terms, and get insights.
            </p>
          </div>
          <button type="button" className="ws-upload-dialog__close" aria-label="Close" onClick={onClose}>
            <IconX size={18} />
          </button>
        </div>
        <UploadContract firstRun={firstRun} counterparties={counterparties} onClose={onClose} />
      </div>
    </Dialog>
  );
}
