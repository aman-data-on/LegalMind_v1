/** QA-021: an id read from the page URL reaches only the endpoint its function names. */
import { afterEach, expect, it, vi } from "vitest";

import { api } from "@/lib/api";

afterEach(() => vi.unstubAllGlobals());

it("encodes a traversal id so the browser cannot normalise it into another endpoint", async () => {
  const fetchMock = vi.fn(async (_target: string) => new Response("{}", { status: 404 }));
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("document", { cookie: "legalmind_csrf=tok" });

  await api.deleteConversation("../contracts/AAA/archive?").catch(() => undefined);
  await api.archiveContract("../x#").catch(() => undefined);

  const paths = fetchMock.mock.calls.map(
    ([target]) => new URL(String(target), "https://h").pathname);
  expect(paths).toEqual([
    "/api/v1/conversations/..%2Fcontracts%2FAAA%2Farchive%3F",
    "/api/v1/contracts/..%2Fx%23/archive",
  ]);
});
