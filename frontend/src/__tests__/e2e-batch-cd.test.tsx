/** E2E fix batch C/D leftovers (6a, 6i): one Publish confirmation, the check on drafts only. */
import { isValidElement, type ReactElement, type ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { checksOnLoad, PublishConfirm } from "@/components/templates/TemplateApproval";

/** The elements under ``node`` (props.children, depth first) — no DOM needed. */
function walk(node: ReactNode, out: ReactElement[] = []): ReactElement[] {
  if (Array.isArray(node)) node.forEach((n) => walk(n, out));
  else if (isValidElement(node)) {
    out.push(node);
    walk((node.props as { children?: ReactNode }).children, out);
  }
  return out;
}

describe("the header Publish dialog (E2E 6a)", () => {
  it("asks once, names the version, and its Publish makes exactly one call", () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    const tree = PublishConfirm({ version: 2, onCancel, onConfirm });
    // the Dialog portals into the page; its content is read from the element tree
    const html = renderToStaticMarkup(<>{(tree.props as { children: ReactNode }).children}</>);
    expect(html).toContain("Publish version 2?");
    expect(html).toContain("Contracts already made keep their version.");
    const buttons = walk(tree).filter((e) => e.type === "button");
    const label = (e: ReactElement) => (e.props as { children: ReactNode }).children;
    expect(buttons.map(label)).toEqual(["Cancel", "Publish"]);
    (buttons[1]!.props as { onClick: () => void }).onClick();
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(onCancel).not.toHaveBeenCalled();
  });
});

describe("the template check runs on drafts only (E2E 6i)", () => {
  it("never checks a published or retired version", () => {
    expect(checksOnLoad({ status: "DRAFT" })).toBe(true);
    expect(checksOnLoad({ status: "PUBLISHED" })).toBe(false);
    expect(checksOnLoad({ status: "RETIRED" } as never)).toBe(false);
    expect(checksOnLoad(null)).toBe(false);
  });
});
