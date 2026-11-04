"use client";

/** Contracts home's "New contract" (S5): make ours from a published template, or upload a
 *  contract (the existing upload, unchanged). Two choices, two lines each. */

import Link from "next/link";

import { Dialog } from "@/components/Dialog";
import "./newcontract.css";

export function NewContractChooser({ onUpload, onClose }: { onUpload: () => void; onClose: () => void }) {
  return (
    <Dialog onClose={onClose} titleId="nc-choose-title">
      <h2 id="nc-choose-title">New contract</h2>
      <ul className="nc-results nc-choose">
        <li>
          <Link className="nc-item" href="/contracts/new" onClick={onClose}>
            <span className="nc-item__l1">Create from our template</span>
            <span className="nc-item__l2">Our NDA or MSA, filled in with the client&rsquo;s details</span>
          </Link>
        </li>
        <li>
          <button type="button" className="nc-item" onClick={onUpload}>
            <span className="nc-item__l1">Upload a contract</span>
            <span className="nc-item__l2">The client&rsquo;s paper, or a contract signed elsewhere</span>
          </button>
        </li>
      </ul>
      <div className="ws-modal__acts">
        <button type="button" className="ws-btn" onClick={onClose}>Cancel</button>
      </div>
    </Dialog>
  );
}
