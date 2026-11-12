"use client";

/**
 * A screen retired for a reader (UX Batch 2, owner 2026-11-11 "go with your
 * recommendation"): the legacy Reviews and Research screens are Legal's. A reader without
 * `legal.review` is sent to Contracts, the nav's own word; nothing is fetched first.
 * Presentation only — the server still scopes every list (rule 18).
 */

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { LoadingState } from "@/components/Feedback";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";

export function LegalOnly({ children }: { children: React.ReactNode }) {
  const { can } = useSession();
  const router = useRouter();
  const allowed = can(P.LEGAL_REVIEW);
  useEffect(() => { if (!allowed) router.replace("/contracts"); }, [allowed, router]);
  return allowed ? <>{children}</> : <LoadingState label="Opening Contracts…" />;
}
