"use client";

/** `/contracts/new` (S5) — our NDA or MSA for a client, from a published template. Absent
 *  (the unknown-address page) for a reader who may not create and upload a contract. */

import { Suspense } from "react";

import { NotHere } from "@/app/templates/NotHere";
import { NewContract } from "@/components/newcontract/NewContract";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";

export default function NewContractPage() {
  const { can } = useSession();
  if (!(can(P.CONTRACT_CREATE) && can(P.DOCUMENT_UPLOAD))) return <NotHere />;
  return <Suspense fallback={null}><NewContract /></Suspense>;
}
