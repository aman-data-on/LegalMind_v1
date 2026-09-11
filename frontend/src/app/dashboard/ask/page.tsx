"use client";

/**
 * Ask — the AI workspace (owner instruction, 2026-09-11), replacing the
 * conversation-history table that carried this name. The rail holds the record;
 * the centre is where a question is actually asked. `?id=` selects one
 * conversation, at the same fixed pathname as before, so every link already
 * handed out still lands on the same chat.
 */

import { Suspense } from "react";

import { AskWorkspace } from "@/components/workspace/AskWorkspace";

export default function AskPage() {
  return (
    <Suspense fallback={null}>
      <AskWorkspace />
    </Suspense>
  );
}
