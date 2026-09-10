"use client";

/**
 * Client Profiles — owner instruction, 2026-09-10.
 *
 * One client, and everything we have with them: who they are, every legal
 * document filed under them in ONE list, each document's version history, and
 * the existing LegalMind review of each.
 *
 * **Nothing here is a second system.** A client is the `counterparties` row
 * AB-13 created; a client's documents are the contracts already linked to it;
 * a document's versions are the `document_versions` rows that were always
 * there; and the analysis is the existing engine reached through the existing
 * workspace. This screen adds an organising layer and no storage.
 *
 * The directory and one client's workspace both live at the fixed pathname
 * `/dashboard/clients`; which one renders is decided by `?id=` rather than a
 * path segment, so no record id appears in the URL path itself — the same
 * convention `/dashboard` and `/dashboard/ask` already follow.
 */

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { ClientDirectory } from "@/components/clients/ClientDirectory";
import { ClientWorkspace } from "@/components/clients/ClientWorkspace";

function ClientsRouteInner() {
  const clientId = useSearchParams().get("id");
  return clientId ? (
    // Keyed, so switching clients in the rail remounts rather than leaving the
    // previous client's tab, notes draft and open version rows behind.
    <ClientWorkspace key={clientId} clientId={clientId} />
  ) : (
    <ClientDirectory />
  );
}

export default function ClientsRoute() {
  return (
    <Suspense fallback={null}>
      <ClientsRouteInner />
    </Suspense>
  );
}
