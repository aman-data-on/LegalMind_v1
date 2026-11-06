import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { BellToggle, NotificationPanel } from "@/components/workspace/Notifications";
import { fileable } from "@/components/workspace/FileIntoContract";
import type { ChatAttachment } from "@/lib/types";

const noop = () => undefined;

describe("notifications (AM-273 m3)", () => {
  it("shows the server's fixed sentence and link, unread said in words, no counter", () => {
    const html = renderToStaticMarkup(<NotificationPanel onClose={noop} reload={noop} list={{
      unread: 1,
      items: [{ id: "n1", kind: "CLIENT_RETURNED", link: "/contracts/c1/changes",
                sentence: "The client returned a new version of Synthetic MSA.",
                created_at: "2026-11-02T10:00:00Z", read_at: null }],
    }} />);
    expect(html).toContain("The client returned a new version of Synthetic MSA.");
    expect(html).toContain('href="/contracts/c1/changes"');
    expect(html).toContain("Unread");
    expect(html).toContain("Mark all as read");
  });

  it("the bell carries a dot and an accessible count, never a number badge", () => {
    const html = renderToStaticMarkup(<BellToggle unread={3} open={false} onClick={noop} />);
    expect(html).toContain('aria-label="Notifications, 3 unread"');
    expect(html).toContain("ws-shell__belldot");
    expect(html).not.toMatch(/>3</);
    expect(renderToStaticMarkup(<BellToggle unread={0} open={false} onClick={noop} />))
      .not.toContain("belldot");
  });
});

describe("File into a contract (AM-269 r2)", () => {
  const base: ChatAttachment = {
    id: "a1", kind: "FILE", filename: "returned.docx", byte_size: 10, status: "READY",
    mime_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    failure_code: null, created_at: "", expires_at: "",
  };
  it("is offered only for a READY Word or PDF file, never a paste or a failed read", () => {
    expect(fileable(base)).toBe(true);
    expect(fileable({ ...base, mime_type: "application/pdf" })).toBe(true);
    expect(fileable({ ...base, kind: "PASTE", mime_type: "text/plain" })).toBe(false);
    expect(fileable({ ...base, status: "FAILED" })).toBe(false);
    expect(fileable({ ...base, mime_type: "text/plain" })).toBe(false);
  });
});
