"use client";

/** Contracts home's "New contract" (S5): make ours from a published template, start from our
 *  own contract the client returned marked up (batch 5), or upload a contract (the existing
 *  upload). Two lines each; the first names only the types published now (`AM-316`), and is
 *  no link when none is. The returned-markup row needs the same rights as its page (N8). */

import Link from "@/components/AppLink";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { RETURNED_COPY } from "@/lib/labels";
import { DOC_TYPES } from "@/lib/newContract";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";

import { Dialog } from "@/components/Dialog";
import "./newcontract.css";

export function NewContractChooser({ onUpload, onClose }: { onUpload: () => void; onClose: () => void }) {
  const { can } = useSession();
  const [types, setTypes] = useState<string[] | null>(null);
  useEffect(() => {
    api.publishedTemplates().then((rows) => setTypes(DOC_TYPES.filter((t) => rows.some((r) => r.doc_type === t.id)).map((t) => t.name)))
      .catch(() => setTypes(null));
  }, []);
  const none = types !== null && !types.length;
  const line = none ? "No template is published yet"
    : `Our ${types ? types.join(" or ") : "NDA or MSA"}, filled in with the client\u2019s details`;
  return (
    <Dialog onClose={onClose} titleId="nc-choose-title">
      <h2 id="nc-choose-title">New contract</h2>
      <ul className="nc-results nc-choose">
        <li>
          {none ? (
            <p className="nc-item nc-item--static">
              <span className="nc-item__l1">Create from our template</span>
              <span className="nc-item__l2">{line}</span>
            </p>
          ) : (
            <Link className="nc-item" href="/contracts/new" onClick={onClose}>
              <span className="nc-item__l1">Create from our template</span>
              <span className="nc-item__l2">{line}</span>
            </Link>
          )}
        </li>
        {can(P.CONTRACT_CREATE) && can(P.DOCUMENT_UPLOAD) ? (
          <li>
            <Link className="nc-item" href="/contracts/new/returned" onClick={onClose}>
              <span className="nc-item__l1">{RETURNED_COPY.choose}</span>
              <span className="nc-item__l2">{RETURNED_COPY.chooseLine}</span>
            </Link>
          </li>
        ) : null}
        <li>
          <button type="button" className="nc-item" onClick={onUpload}>
            <span className="nc-item__l1">Upload a contract</span>
            <span className="nc-item__l2">{RETURNED_COPY.uploadLine}</span>
          </button>
        </li>
      </ul>
      <div className="ws-modal__acts">
        <button type="button" className="ws-btn" onClick={onClose}>Cancel</button>
      </div>
    </Dialog>
  );
}
