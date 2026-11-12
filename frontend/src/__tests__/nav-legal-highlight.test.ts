import { describe, expect, it } from "vitest";

import { navItemsFor } from "@/components/workspace/model";
import * as P from "@/lib/permissions";

describe("To-do lights for the Legal queue only for whoever may open it", () => {
  const todo = (can: (p: string) => boolean) => navItemsFor(can).find((i) => i.href === "/todo");
  it("a seller on the no-access page: To-do stays dark", () => {
    expect(todo((p) => p === P.CONTRACT_VIEW)?.also).not.toContain("/dashboard/legal");
  });
  it("a lawyer: the Legal queue is a To-do view", () => {
    expect(todo((p) => p === P.CONTRACT_VIEW || p === P.LEGAL_REVIEW)?.also).toContain("/dashboard/legal");
  });
});
