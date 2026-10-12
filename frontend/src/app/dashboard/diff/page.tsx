"use client";

/**
 * Diff-Talk — two documents side by side (owner, 2026-10-12). `?left=` and
 * `?right=` name the two sides (a document version id or a website document key),
 * so a comparison is a link like every other screen here.
 */

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { DiffTalkPage } from "@/components/workspace/DiffTalk";

function DiffRoute() {
  const params = useSearchParams();
  const router = useRouter();
  return (
    <DiffTalkPage
      initialLeft={params.get("left") ?? ""}
      initialRight={params.get("right") ?? ""}
      onChange={(left, right) => {
        const q = new URLSearchParams();
        if (left) q.set("left", left);
        if (right) q.set("right", right);
        router.replace(`/dashboard/diff${q.size ? `?${q}` : ""}`, { scroll: false });
      }}
    />
  );
}

export default function DiffPage() {
  return (
    <Suspense fallback={null}>
      <DiffRoute />
    </Suspense>
  );
}
