"use client";

/**
 * Ask — the AI workspace (owner instruction, 2026-09-11).
 *
 * What this replaces, and why
 * --------------------------
 * `/dashboard/ask` was a four-column table of past questions with the heading
 * "Ask · 1 total" and a sentence telling the reader that asking happens
 * somewhere else. The capability the nav advertised could not be exercised on
 * the page that carried its name. Ask is now the workspace itself: a rail of
 * recent chats, a conversation, and a composer — and a question can be asked
 * before any document exists, which the assist lane has supported since
 * 2026-09-08 (a document-less conversation) but no screen offered.
 *
 * What is NOT changed, deliberately
 * ---------------------------------
 * Every rule the dock already obeys holds here, because this is the same
 * capability on a different surface:
 *
 *   · the question picks the sources — never a mode selector (`assist.routing`)
 *   · a compliance-shaped question is ROUTED to the deterministic evaluator and
 *     answered by its Findings (`AM-25` r4); this screen renders those Findings
 *     as the table the owner asked for and generates no row of its own
 *   · one refusal sentence, whatever the cause (`AM-29` r4), on the quiet
 *     surface — the system working, not failing
 *   · a citation points at its evidence row, and opens the document there
 *     (`?evidence=`), on the version the answer was read from
 *   · retrieval scores are never rendered as legal confidence (rule 12)
 *
 * The in-document dock (`AskDock`, DD-15/DD-17 r4) stays exactly as it is: a
 * reader inside a document asks there, about the version on screen. This screen
 * is the way in when there is no document open yet — and the record of both.
 *
 * Attaching a file
 * ----------------
 * Attaching a document to a chat that has none KEEPS THE THREAD (2026-09-11,
 * `POST /conversations/{id}/document`). A reader who has been asking what the
 * organization requires and then attaches the agreement can say "now compare
 * this with our standards" and mean it — the earlier turns are still there, and
 * the answer is about the document they just supplied.
 *
 * A chat that already HAS a document starts a new one instead, and the screen
 * says so before it happens. That is not a UI shortcut: earlier turns cite
 * `evidence_id`s belonging to the first document's reading order, and moving
 * the scope underneath them would leave every one of those citations pointing
 * at a row the conversation no longer contains. The server refuses it too.
 *
 * The upload is the same two calls the intake makes; the analysis chain runs
 * behind it exactly as it does from the Dashboard, so a comparison question has
 * a Review to be answered from as soon as the evaluator finishes.
 */

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { chainAnalysis } from "@/lib/analysisChain";
import { ApiError, api, describeError } from "@/lib/api";
import { nameFromFilename } from "@/lib/documentTypes";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { AskResult, ConversationSummary, ConversationTurn } from "@/lib/types";

import {
  IconFile,
  IconSearch,
  IconMessage,
  IconPaperclip,
  IconPlus,
  IconSend,
  IconSparkle,
  IconX,
} from "./icons";
import { TranscriptTurn } from "./TranscriptTurn";

/** Mirrors the server's own limit (`LEGALMIND_MAX_UPLOAD_BYTES`) and the
 *  intake's pre-check — a friendly message before a 25 MB round trip. The
 *  server's validation stays the authority (34.16). */
const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;
const SUPPORTED_EXTENSIONS = [".pdf", ".docx"];

function preflightProblem(file: File): string | null {
  const name = file.name.toLowerCase();
  if (!SUPPORTED_EXTENSIONS.some((extension) => name.endsWith(extension))) {
    return "Only PDF and DOCX files can be attached.";
  }
  if (file.size > MAX_UPLOAD_BYTES) return "That file is larger than 25 MB.";
  if (file.size === 0) return "That file is empty.";
  return null;
}

/** Openers, as editable drafts — nothing sends until the reader sends it. Two
 *  about the organization's own approved material (answerable with no document
 *  attached) and two about an attached agreement. */
const OPENERS = [
  "What standards do we require for liability?",
  "Explain our termination standard.",
  "What is the termination notice period?",
  "Compare this agreement with our standards.",
];

/** Today / Yesterday / date — the rail's grouping, from the row's own timestamp. */
function dayGroup(iso: string | null): string {
  if (!iso) return "Earlier";
  const then = new Date(iso);
  const midnight = new Date();
  midnight.setHours(0, 0, 0, 0);
  if (then.getTime() >= midnight.getTime()) return "Today";
  if (then.getTime() >= midnight.getTime() - 86_400_000) return "Yesterday";
  return then.toISOString().slice(0, 10);
}

/** The conversation's title: the first thing the reader actually asked. */
function chatTitle(conversation: ConversationSummary): string {
  return conversation.first_question?.trim() || "New chat";
}

/** A live answer in the recorded turn's shape, so ONE renderer draws both — the
 *  replayed transcript and the answer that has just arrived. */
function liveTurns(question: string, result: AskResult): ConversationTurn[] {
  return [
    {
      id: `${result.message_id}-q`,
      ordinal: -1,
      role: "USER",
      content: question,
      answer_state: null,
      routed_to_evaluator: false,
      document_version_id: null,
      version_number: null,
      citations: [],
    },
    {
      id: result.message_id,
      ordinal: 0,
      role: "ASSISTANT",
      content: result.text,
      answer_state: result.answer_state,
      routed_to_evaluator: result.routed_to_evaluator,
      document_version_id: result.document_version_id,
      version_number: result.version_number,
      citations: result.citations,
      positions: result.positions ?? [],
      statutes: result.statutes ?? null,
    },
  ];
}

interface Scope {
  contractId: string | null;
  documentName: string | null;
}

export function AskWorkspace() {
  const { can } = useSession();
  const activeId = useSearchParams().get("id");

  const [conversations, setConversations] = useState<ConversationSummary[] | null>(null);
  const [turns, setTurns] = useState<ConversationTurn[]>([]);
  const [scope, setScope] = useState<Scope>({ contractId: null, documentName: null });
  const [loadingChat, setLoadingChat] = useState(false);
  const [notFound, setNotFound] = useState(false);
  const [question, setQuestion] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const [attachment, setAttachment] = useState<File | null>(null);
  const [search, setSearch] = useState("");
  /** The version a question is about, once the chat has a document. Named
   *  explicitly rather than left to the server's "newest" default, for the same
   *  reason the dock names it: a citation's `evidence_id` belongs to exactly one
   *  version's reading order. */
  const [versionId, setVersionId] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  /** The Review whose Findings answer a routed comparison turn. */
  const [reviewId, setReviewId] = useState<string | null>(null);

  const railRef = useRef<HTMLDetailsElement>(null);
  const logRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const busy = pending !== null;

  const canAsk = can(P.ASSIST_ASK);
  const canUpload = can(P.CONTRACT_CREATE) && can(P.DOCUMENT_UPLOAD);

  const loadConversations = useCallback(async () => {
    try {
      const { items } = await api.conversations({ page_size: 50 });
      setConversations(items);
    } catch {
      // The rail is orientation; asking works without it.
      setConversations([]);
    }
  }, []);

  useEffect(() => {
    if (canAsk) void loadConversations();
  }, [canAsk, loadConversations]);

  // The open conversation, replayed with the citations it carried live
  // (`AM-25` r5). `?id=` is the only selector — so a chat is a shareable URL.
  useEffect(() => {
    let cancelled = false;
    setNotFound(false);
    setError(null);
    setReviewId(null);
    if (!activeId) {
      setTurns([]);
      setScope({ contractId: null, documentName: null });
      setVersionId(null);
      return;
    }
    setLoadingChat(true);
    (async () => {
      try {
        const detail = await api.conversation(activeId);
        if (cancelled) return;
        setTurns(detail.messages);
        let documentName: string | null = null;
        if (detail.contract_id) {
          try {
            const contract = await api.contract(detail.contract_id);
            documentName = contract.name;
            setVersionId(contract.document_versions?.[0]?.id ?? null);
          } catch {
            // A document since archived or out of scope: the conversation is
            // still the caller's own and still readable (`AM-25` r7).
          }
        }
        if (!cancelled) setScope({ contractId: detail.contract_id, documentName });
      } catch (cause) {
        if (cancelled) return;
        if (cause instanceof ApiError && cause.isNotFound) setNotFound(true);
        else setError(cause);
      } finally {
        if (!cancelled) setLoadingChat(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activeId]);

  /* A routed turn is answered by the evaluator's Findings, so the table needs a
   * Review. A live routing hands one over; a REPLAYED one does not (the stored
   * turn carries no comparison), so the document's most recent Review is
   * resolved instead — the same Review the workspace itself would open. */
  useEffect(() => {
    if (reviewId || !scope.contractId) return;
    if (!turns.some((turn) => turn.routed_to_evaluator)) return;
    let cancelled = false;
    (async () => {
      try {
        const { items } = await api.reviews({ contract_id: scope.contractId!, page_size: 1 });
        if (!cancelled && items[0]) setReviewId(items[0].id);
      } catch {
        // No Review, or no permission to see one: the turn keeps its own words.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [turns, scope.contractId, reviewId]);

  /* The rail is a native <details>: open on a desktop, closed on a phone, where
   * it is a drawer and would otherwise cost half the screen before a single
   * word is read. Set once, imperatively, because `open` is the element's own
   * state from then on — the reader's toggle must not be overridden on every
   * render. Matches the CSS breakpoint that turns the summary into a control. */
  useEffect(() => {
    const rail = railRef.current;
    if (rail) rail.open = !window.matchMedia("(max-width: 860px)").matches;
  }, []);

  // The newest turn is what the reader wants to see. Scrolling the LOG, never
  // the page: a long answer must not move the rail or the composer.
  useEffect(() => {
    const node = logRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [turns.length, pending]);

  function chooseFile(file: File | null) {
    if (!file) return;
    const problem = preflightProblem(file);
    if (problem) {
      setError(problem);
      return;
    }
    setError(null);
    setAttachment(file);
    inputRef.current?.focus();
  }

  const submit = useCallback(async () => {
    const asked = question.trim();
    if (!asked || busy) return;
    setPending(asked);
    setQuestion("");
    setError(null);
    const file = attachment;
    try {
      let conversationId = activeId;
      let contractId = scope.contractId;

      if (file) {
        const contract = await api.createContract(nameFromFilename(file.name));
        const uploaded = await api.uploadDocument(contract.id, file);
        contractId = contract.id;
        if (conversationId && scope.contractId === null) {
          // THE THREAD SURVIVES. This chat has no document yet, so it gains one
          // and every earlier turn stays readable — which is what makes "now
          // compare this with our standards" a sentence a person can actually
          // type after five turns about the standards themselves.
          await api.attachDocument(conversationId, contract.id);
        } else {
          // It already has one. A second document starts a new chat rather than
          // re-pointing this one: earlier citations belong to the FIRST
          // document's reading order and would be stranded. The server refuses
          // it as well — this branch is the honest UI, not the enforcement.
          const created = await api.createConversation(contract.id);
          conversationId = created.id;
          setTurns([]);
        }
        setScope({ contractId: contract.id, documentName: contract.name });
        setVersionId(uploaded.document_version.id);
        setAttachment(null);
        // The analysis runs behind the conversation rather than in front of it
        // — the reader asked a question, not for a Review. Best-effort exactly
        // as it is from the Dashboard; the workspace states the real situation.
        void chainAnalysis(contract.id, can(P.REVIEW_CREATE));
      } else if (!conversationId) {
        const created = await api.createConversation(null);
        conversationId = created.id;
      }

      const result = await api.ask(conversationId, asked,
                                   versionId ?? undefined);
      setTurns((previous) => [...previous, ...liveTurns(asked, result)]);
      if (result.comparison?.review_id) setReviewId(result.comparison.review_id);
      if (conversationId !== activeId) {
        // The URL becomes the conversation's address without a navigation —
        // remounting here would refetch the turns that just arrived.
        const url = new URL(window.location.href);
        url.searchParams.set("id", conversationId);
        window.history.replaceState(null, "", url);
      }
      void loadConversations();
    } catch (cause) {
      setError(cause);
    } finally {
      setPending(null);
    }
  }, [activeId, attachment, busy, can, loadConversations, question, scope.contractId,
      versionId]);

  if (!canAsk) {
    return (
      <div className="ws-state" role="note">
        <h2>Access restricted</h2>
        <p>Your account does not include Ask access.</p>
      </div>
    );
  }

  /* The filter matches the question AND the document name, because "CloudPe" is
     as likely a way to find a chat as "termination". Case-insensitive, substring —
     no ranking, because a list of fifty is not a search problem. */
  const needle = search.trim().toLowerCase();
  const visible = (conversations ?? []).filter((conversation) =>
    needle === "" ||
    chatTitle(conversation).toLowerCase().includes(needle) ||
    (conversation.document_name ?? "").toLowerCase().includes(needle));

  const groups: { day: string; items: ConversationSummary[] }[] = [];
  for (const conversation of visible) {
    const day = dayGroup(conversation.created_at);
    const last = groups[groups.length - 1];
    if (last && last.day === day) last.items.push(conversation);
    else groups.push({ day, items: [conversation] });
  }

  return (
    <div className="ws-chat">
      {/* ---- recent chats ------------------------------------------------ */}
      {/* A native disclosure: open at every width the CSS leaves it open at,
          and a real drawer on a phone with no state to keep in sync. */}
      <details className="ws-chat__rail" ref={railRef} open>
        <summary className="ws-chat__railtoggle">
          <IconMessage size={15} /> Recent chats
        </summary>
        <div className="ws-chat__railbody">
          <h2 className="ws-chat__railhead">
            <IconMessage size={13} /> Recent chats
          </h2>
          <Link
            className="ws-btn ws-btn--primary ws-chat__new"
            href="/dashboard/ask"
            onClick={() => {
              setTurns([]);
              setAttachment(null);
              setScope({ contractId: null, documentName: null });
            }}
          >
            <IconPlus size={15} /> New chat
          </Link>
          {/* Filters what is ALREADY loaded. `GET /conversations` allow-lists only
              `contract_id` (49.6 r3), so there is no server-side search to call and
              none is invented here — the field says it searches this list. */}
          <div className="ws-chat__search">
            <IconSearch size={14} />
            <label className="ws-visually-hidden" htmlFor="ws-chat-search">
              Search your chats
            </label>
            <input
              id="ws-chat-search"
              type="search"
              value={search}
              placeholder="Search chats…"
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
          <nav aria-label="Recent chats">
            {conversations === null ? (
              <p className="ws-pane__note" role="status" aria-live="polite">
                Loading…
              </p>
            ) : conversations.length === 0 ? (
              <p className="ws-chat__railempty">
                No conversations yet. Ask something and it is kept here.
              </p>
            ) : visible.length === 0 ? (
              // A different fact from "you have no chats", and said differently.
              <p className="ws-chat__railempty">
                No chat matches &ldquo;{search.trim()}&rdquo;.
              </p>
            ) : (
              groups.map((group) => (
                <div key={group.day} className="ws-chat__railgroup">
                  <h2 className="ws-chat__railday">{group.day}</h2>
                  <ul className="ws-chat__raillist">
                    {group.items.map((conversation) => (
                      <li key={conversation.id}>
                        <Link
                          className="ws-chat__railitem"
                          href={`/dashboard/ask?id=${conversation.id}`}
                          aria-current={conversation.id === activeId ? "page" : undefined}
                        >
                          <span className="ws-chat__railname">{chatTitle(conversation)}</span>
                          <span className="ws-chat__railmeta">
                            {conversation.contract_id ? (
                              <>
                                <IconFile size={12} />{" "}
                                {conversation.document_name ?? "Document"}
                              </>
                            ) : (
                              <>
                                <IconSparkle size={12} /> Company knowledge
                              </>
                            )}
                          </span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                </div>
              ))
            )}
          </nav>
        </div>
      </details>

      {/* ---- the conversation -------------------------------------------- */}
      <section className="ws-chat__main" aria-label="Conversation">
        <header className="ws-chat__head">
          <h1 className="ws-chat__title">
            {activeId && conversations
              ? (conversations.find((c) => c.id === activeId)
                  ? chatTitle(conversations.find((c) => c.id === activeId)!)
                  : "Conversation")
              : "Ask LegalMind"}
          </h1>
          <p className="ws-chat__scope">
            {scope.contractId ? (
              <>
                <IconFile size={13} /> About{" "}
                <Link href={`/dashboard?id=${scope.contractId}`}>
                  {scope.documentName ?? "this document"}
                </Link>{" "}
                — and the organization&rsquo;s approved standards.
              </>
            ) : (
              <>
                <IconSparkle size={13} /> Answered from the organization&rsquo;s approved
                standards and the approved statute corpus. Attach a document to ask about
                one.
              </>
            )}
          </p>
        </header>

        <div className="ws-chat__log" ref={logRef} tabIndex={-1}>
          <div className="ws-chat__thread">
            {notFound ? (
              <div className="ws-state" role="note">
                <h2>Not found.</h2>
                <p>
                  <Link href="/dashboard/ask">Start a new chat</Link>.
                </p>
              </div>
            ) : null}

            {loadingChat ? (
              <div aria-busy="true">
                <p className="ws-visually-hidden" role="status" aria-live="polite">
                  Loading the conversation…
                </p>
                <span className="ws-skel ws-skel--line" style={{ width: "38%" }} aria-hidden="true" />
                <span className="ws-skel ws-skel--line" style={{ width: "80%" }} aria-hidden="true" />
              </div>
            ) : null}

            {!loadingChat && !notFound && turns.length === 0 && pending === null ? (
              <div className="ws-chat__welcome">
                <span className="ws-chat__welcomemark" aria-hidden="true">
                  <IconSparkle size={20} />
                </span>
                <h2>Ask about a document, or about what we require.</h2>
                <p>
                  Every answer quotes the passage it came from, or says plainly that the
                  approved material does not answer the question. A question about whether a
                  document meets our standards is answered by the evaluator&rsquo;s own
                  Findings, never by the assistant.
                </p>
                <div className="ws-chat__openers" role="group" aria-label="Example questions">
                  {OPENERS.map((opener) => (
                    <button
                      key={opener}
                      type="button"
                      disabled={busy}
                      onClick={() => {
                        setQuestion(opener);
                        inputRef.current?.focus();
                      }}
                    >
                      {opener}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}

            {turns.map((turn) => (
              <TranscriptTurn
                key={turn.id}
                turn={turn}
                contractId={scope.contractId}
                comparisonReviewId={turn.routed_to_evaluator ? reviewId : null}
              />
            ))}

            {pending !== null ? (
              <>
                <div className="ws-turn ws-turn--user">
                  <p className="ws-ask__q">
                    <span className="ws-ask__role">You</span> {pending}
                  </p>
                </div>
                <div className="ws-turn">
                  <div className="ws-ask__answer" aria-busy="true">
                    <p className="ws-pane__note" role="status" aria-live="polite">
                      Looking this up and checking citations…
                    </p>
                    <span className="ws-skel ws-skel--line" style={{ width: "88%" }} aria-hidden="true" />
                    <span className="ws-skel ws-skel--line" style={{ width: "64%" }} aria-hidden="true" />
                  </div>
                </div>
              </>
            ) : null}

            {error ? (
              <div className="ws-state ws-state--error" role="alert">
                <p>
                  {typeof error === "string" ? error : describeError(error)}
                </p>
                <button
                  type="button"
                  className="ws-btn ws-btn--sm"
                  onClick={() => {
                    setError(null);
                    setQuestion(pending ?? question);
                    inputRef.current?.focus();
                  }}
                >
                  Try again
                </button>
              </div>
            ) : null}
          </div>
        </div>

        {/* ---- composer --------------------------------------------------- */}
        <form
          className="ws-chat__composer"
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
          }}
        >
          {attachment ? (
            <div className="ws-chat__files">
              <span className="ws-chat__file">
                <IconFile size={13} />
                <span className="ws-chat__filename">{attachment.name}</span>
                <button
                  type="button"
                  onClick={() => setAttachment(null)}
                  aria-label={`Remove ${attachment.name}`}
                >
                  <IconX size={13} />
                </button>
              </span>
              <span className="ws-chat__filenote">
                {scope.contractId === null
                  ? "This chat will be about this document. Your earlier questions stay."
                  : "This chat is already about a document — sending starts a new one."}
              </span>
            </div>
          ) : null}

          <div className="ws-chat__inputrow">
            {canUpload ? (
              <>
                <input
                  ref={fileRef}
                  className="ws-visually-hidden"
                  type="file"
                  accept=".pdf,.docx"
                  onChange={(event) => {
                    chooseFile(event.target.files?.[0] ?? null);
                    event.target.value = "";
                  }}
                />
                <button
                  type="button"
                  className="ws-chat__attach"
                  onClick={() => fileRef.current?.click()}
                  disabled={busy}
                >
                  <IconPaperclip size={15} />
                  <span>Add files</span>
                </button>
              </>
            ) : null}
            <label className="ws-visually-hidden" htmlFor="ws-chat-question">
              Your question
            </label>
            <textarea
              id="ws-chat-question"
              ref={inputRef}
              className="ws-chat__input"
              value={question}
              rows={1}
              maxLength={2000}
              placeholder="Ask LegalMind…"
              disabled={busy}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={(event) => {
                // Enter sends, Shift+Enter breaks the line — the composer
                // convention. A textarea is what lets a long question be read
                // back before it is sent.
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void submit();
                }
              }}
            />
            <button
              className="ws-chat__send"
              type="submit"
              aria-label={busy ? "Searching…" : "Send question"}
              disabled={busy || !question.trim()}
            >
              <IconSend size={16} />
            </button>
          </div>
          <p className="ws-chat__note">
            Answers cite the material they came from, or say they cannot. Verify against the
            original document.
          </p>
        </form>
      </section>
    </div>
  );
}
