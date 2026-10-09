/**
 * Answer feedback (`AM-123`, owner D2c 2026-10-08; DD-26) — static render, house idiom.
 *
 * 1. Every assistant turn carries two plain-word buttons, nothing pressed and no reason
 *    field until the server has a "Not helpful"; no counts, no score, no learning claim.
 * 2. `feedback()` posts through the CSRF header with `keepalive`, never `sendBeacon`.
 * 3. The implicit signals: a click on a source counts, a click elsewhere does not, each
 *    kind is sent once per answer, and quick-close is "under five seconds" — leaving
 *    the chat, never the chat's own address, never by following one of its sources.
 * 4. A rating shows as recorded only after the server has it.
 */
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  AnswerFeedback,
  closedQuickly,
  quickCloser,
  sendRating,
  signalsOn,
  TranscriptTurn,
} from "@/components/workspace/TranscriptTurn";
import { feedback } from "@/lib/api";
import type { ConversationTurn } from "@/lib/types";

/** The kinds posted so far, in order. */
function kinds(fetchMock: ReturnType<typeof vi.fn>): string[] {
  return fetchMock.mock.calls.map((c) =>
    JSON.parse((c as unknown as [string, RequestInit])[1].body as string).kind);
}

function stubFetch(response: () => Promise<Response> = async () =>
  new Response(JSON.stringify({ data: { id: "f" } }), { status: 201 })) {
  const fetchMock = vi.fn(response);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function turn(overrides: Partial<ConversationTurn>): ConversationTurn {
  return {
    id: "m-1", ordinal: 1, role: "ASSISTANT", content: "Twelve months.",
    answer_state: "ANSWERED", routed_to_evaluator: false, document_version_id: null,
    version_number: null, citations: [], ...overrides,
  };
}

afterEach(() => vi.unstubAllGlobals());

describe("the rating control", () => {
  it("is two plain words on every assistant turn, nothing pressed, no reason yet", () => {
    for (const t of [turn({}), turn({ answer_state: "NO_EVIDENCE_RETRIEVED" }),
                     turn({ routed_to_evaluator: true })]) {
      const html = renderToStaticMarkup(<TranscriptTurn turn={t} contractId={null} />);
      expect(html).toContain('role="group" aria-label="Rate this answer"');
      expect(html).toContain('aria-pressed="false">Helpful</button>');
      expect(html).toContain('aria-pressed="false">Not helpful</button>');
      expect(html).not.toContain("What was wrong");
    }
    const user = renderToStaticMarkup(
      <TranscriptTurn turn={turn({ role: "USER" })} contractId={null} />);
    expect(user).not.toContain("Helpful");
  });

  it("claims nothing: no count, no score, no learning, no emoji", () => {
    const html = renderToStaticMarkup(<AnswerFeedback messageId="m-1" />);
    expect(html).not.toMatch(/\d|confiden|score|improv|learn|train|thank/i);
    expect(html).not.toMatch(/\p{Extended_Pictographic}/u);
  });
});

describe("feedback()", () => {
  it("posts the signal with keepalive and the CSRF header, and returns the id", async () => {
    vi.stubGlobal("document", { cookie: "legalmind_csrf=tok%3D1" });
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ data: { id: "f-1" } }),
      { status: 201, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    expect(await feedback("m-1", "RATING", "DOWN", "Missed the carve-out")).toEqual(
      { id: "f-1" });
    const [target, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(target).toBe("/api/v1/feedback");
    expect(init).toMatchObject({ method: "POST", keepalive: true, credentials: "same-origin" });
    expect(JSON.parse(init.body as string)).toEqual(
      { message_id: "m-1", kind: "RATING", rating: "DOWN", reason: "Missed the carve-out" });
  });

  it("rejects when the server refuses, so the control never says Recorded", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("{}", { status: 404 })));
    await expect(feedback("m-x", "COPY")).rejects.toMatchObject({ status: 404 });
  });
});

describe("the implicit signals", () => {
  it("count a click on a source and nothing else", () => {
    const fetchMock = vi.fn(async () => new Response("{}", { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);
    const on = signalsOn("m-1");
    on.onClick({ target: { closest: () => null } as unknown as Element });
    expect(fetchMock).not.toHaveBeenCalled();
    const cite = { closest: (s: string) => (s.includes("ws-ask__cite") ? {} : null) };
    on.onClick({ target: cite as unknown as Element });
    on.onCopy();
    const kinds = fetchMock.mock.calls.map((c) =>
      JSON.parse((c as unknown as [string, RequestInit])[1].body as string).kind);
    expect(kinds).toEqual(["CITE_CLICK", "COPY"]);
  });

  it("call a close under five seconds after the answer quick", () => {
    expect(closedQuickly(1000, 5999)).toBe(true);
    expect(closedQuickly(1000, 6000)).toBe(false);
  });

  it("send each kind once per answer, however often the reader copies", () => {
    const fetchMock = stubFetch();
    const on = signalsOn("m-once");
    on.onCopy();
    on.onCopy();
    expect(kinds(fetchMock)).toEqual(["COPY"]);
  });

  it("report a quick close on leaving the chat, not on its own address or later", () => {
    let clock = 0;
    const fetchMock = stubFetch();
    const closer = quickCloser(() => clock);
    closer.show("m-q1", "chat-1");
    closer.chat("chat-1");                 // the chat's own URL being set
    clock = 4999;
    closer.chat("chat-2");                 // switched chat inside five seconds
    closer.show("m-q2", "chat-2");
    clock = 4999 + 5000;
    closer.chat(null);                     // a new chat, too late to count
    closer.show("m-q3", "chat-3");
    closer.leave();                        // pagehide / unmount, inside five seconds
    const ids = fetchMock.mock.calls.map((c) =>
      JSON.parse((c as unknown as [string, RequestInit])[1].body as string).message_id);
    expect(kinds(fetchMock)).toEqual(["QUICK_CLOSE", "QUICK_CLOSE"]);
    expect(ids).toEqual(["m-q1", "m-q3"]);
  });

  it("never call following one of the answer's own sources a quick close", () => {
    const fetchMock = stubFetch();
    const closer = quickCloser(() => 0);
    closer.show("m-cited", "chat-1");
    signalsOn("m-cited").onClick({
      target: { closest: () => ({}) } as unknown as Element });
    closer.leave();                        // the citation link navigated away
    expect(kinds(fetchMock)).toEqual(["CITE_CLICK"]);
  });
});

describe("a rating", () => {
  const initial = { rating: null, status: "", reasonSent: false } as const;

  it("shows as recorded only once the server has it", async () => {
    let resolve: (r: Response) => void = () => undefined;
    stubFetch(() => new Promise<Response>((r) => { resolve = r; }));
    const patches: object[] = [];
    const done = sendRating("m-r", initial, "DOWN", undefined, (p) => patches.push(p));
    expect(patches).toEqual([{ status: "saving" }]);
    resolve(new Response(JSON.stringify({ data: { id: "f" } }), { status: 201 }));
    await done;
    expect(patches.at(-1)).toEqual({ rating: "DOWN", reasonSent: false, status: "Recorded" });
  });

  it("never says recorded when the server refuses", async () => {
    stubFetch(async () => new Response("{}", { status: 429 }));
    const patches: object[] = [];
    await sendRating("m-r", initial, "UP", undefined, (p) => patches.push(p));
    expect(patches).toEqual([{ status: "saving" }, { status: "Not recorded. Try again." }]);
  });

  it("pressed again sends nothing, so a reason already sent stays", async () => {
    const fetchMock = stubFetch();
    const set = vi.fn();
    await sendRating("m-r", { rating: "DOWN", status: "Recorded", reasonSent: true },
                     "DOWN", undefined, set);
    expect(fetchMock).not.toHaveBeenCalled();
    expect(set).not.toHaveBeenCalled();
  });
});
