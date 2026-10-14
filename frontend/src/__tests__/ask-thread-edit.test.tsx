/**
 * Edit waits while any chat is being answered (review, 2026-10-14). Sending is
 * disabled then (`isSendDisabled`), so an edit sent from another chat closed its
 * editor and was dropped without a word. Static render, the house idiom.
 */
import { AssistantRuntimeProvider } from "@assistant-ui/react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { Thread } from "@/components/ui/thread";
import { askedTurn, useAskRuntime } from "@/components/workspace/askThread";

const QUESTION = askedTurn("6f1c2b3a-1d2e-4f50-8a9b-0c1d2e3f4a5b", "What is the cap?");

function Chat({ busy }: { busy: boolean }) {
  const runtime = useAskRuntime({
    turns: [QUESTION], pending: null, busy, send: async () => undefined, stop: () => undefined,
  });
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <Thread empty={false} welcome={{ title: "Ask" }} suggestions={[]} onSuggestion={() => undefined}
              renderAnswer={() => null} progress={null} viewportRef={null} onJump={() => undefined}
              composer={{ inputRef: null, onKeyDown: () => undefined }} />
    </AssistantRuntimeProvider>
  );
}

describe("Editing a question", () => {
  it("is offered when nothing is being answered", () => {
    expect(renderToStaticMarkup(<Chat busy={false} />)).toContain("Edit question");
  });

  it("waits while another chat is being answered", () => {
    const html = renderToStaticMarkup(<Chat busy />);
    expect(html).toContain("What is the cap?");
    expect(html).not.toContain("Edit question");
  });
});
