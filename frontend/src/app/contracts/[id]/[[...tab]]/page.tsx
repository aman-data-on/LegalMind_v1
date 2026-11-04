"use client";

/**
 * One contract — `/contracts/{id}`, `/contracts/{id}/changes`, `/contracts/{id}/versions/{n}`
 * (`AM-263`). The id is read from the path; the rest of the path is tab state the
 * workspace reads with `contractTabFromPath`. Scope is the server's: an id outside the
 * caller's scope is the same 404 as one that does not exist (SEC-07).
 */

import { useParams } from "next/navigation";

import { WorkspacePage } from "@/components/workspace/WorkspacePage";

export default function ContractRoute() {
  const { id } = useParams<{ id: string }>();
  return <WorkspacePage key={id} contractId={id} />;
}
