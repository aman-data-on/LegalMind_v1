"use client";

/** `/contracts/new/returned` (batch 5, AB-221) — our own contract came back marked up.
 *  Absent (the unknown-address page) for a reader who may not create and upload a
 *  contract, exactly as `/contracts/new`. */

import { NotHere } from "@/app/templates/NotHere";
import { ReturnedMarkup } from "@/components/newcontract/ReturnedMarkup";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";

export default function ReturnedMarkupPage() {
  const { can } = useSession();
  if (!(can(P.CONTRACT_CREATE) && can(P.DOCUMENT_UPLOAD))) return <NotHere />;
  return <ReturnedMarkup />;
}
