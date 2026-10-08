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
 * A chat that already HAS a document keeps it, and a further file becomes the
 * chat's material beside it (D6, 2026-10-07: two agreements in one chat): every
 * answer drawn from it names the file. The document itself is never re-pointed —
 * earlier turns cite `evidence_id`s from its reading order, and moving the scope
 * underneath them would strand every one of those citations; the server refuses
 * that too.
 *
 * The upload is the same two calls the intake makes; the analysis chain runs
 * behind it exactly as it does from the Dashboard, so a comparison question has
 * a Review to be answered from as soon as the evaluator finishes.
 */

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";

import { Dialog } from "@/components/Dialog";
import { chainAnalysis } from "@/lib/analysisChain";
import { ASK_TIMEOUT_MS, ApiError, api, describeError } from "@/lib/api";
import { nameFromFilename } from "@/lib/documentTypes";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { AskModel, AskResult, ConversationSummary, ConversationTurn } from "@/lib/types";

import {
  IconChevronDown,
  IconFile,
  IconSearch,
  IconMessage,
  IconPaperclip,
  IconPencil,
  IconPlus,
  IconSend,
  IconSparkle,
  IconTrash,
  IconX,
} from "./icons";
import { scrollMotion } from "./AnswerProse";
import { ChatMaterial } from "./ChatMaterial";
import { ModelPicker } from "./ModelPicker";
import { AiVoice, TranscriptTurn, useQuickClose } from "./TranscriptTurn";

/** Mirrors the server's own limit (`LEGALMIND_MAX_UPLOAD_BYTES`) and the
 *  intake's pre-check — a friendly message before a 25 MB round trip. The
 *  server's validation stays the authority (34.16). */
const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;
const SUPPORTED_EXTENSIONS = [".pdf", ".docx", ".md", ".txt"];

function preflightProblem(file: File): string | null {
  const name = file.name.toLowerCase();
  if (!SUPPORTED_EXTENSIONS.some((extension) => name.endsWith(extension))) {
    return "Only PDF, Word (.docx), Markdown and text files can be attached.";
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
];
/** The fourth opener fits the chat: a comparison needs a document, so a chat without
 *  one offers a question it can answer instead (`AM-109`). */
const DOCUMENT_OPENER = "Compare this agreement with our standards.";
const KNOWLEDGE_OPENER = "Are the DPDP Act's penalties in force yet?";


/** Today / Yesterday / date — the rail's grouping, from the row's own timestamp. The date
 *  is the reader's LOCAL day, like "Today": `toISOString()` gave the UTC day, so a chat at
 *  01:30 IST on 4 Oct sat under "2026-10-03" (2026-10-06). */
export function dayGroup(iso: string | null, now: Date = new Date()): string {
  if (!iso) return "Earlier";
  const then = new Date(iso);
  const midnight = new Date(now);
  midnight.setHours(0, 0, 0, 0);
  if (then.getTime() >= midnight.getTime()) return "Today";
  if (then.getTime() >= midnight.getTime() - 86_400_000) return "Yesterday";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${then.getFullYear()}-${pad(then.getMonth() + 1)}-${pad(then.getDate())}`;
}

/** Enter that commits an IME composition (Devanagari, Japanese, Chinese input) chooses
 *  the composed word; it is not a send. Safari reports it only as keyCode 229. */
export function isImeEnter(event: { nativeEvent: KeyboardEvent; keyCode: number }): boolean {
  return event.nativeEvent.isComposing || event.keyCode === 229;
}

/** The typed question's own cap, the server's (`attachments.QUESTION_MAX_CHARS`). Longer
 *  text is never cut here: the server keeps it as the chat's material, exactly as an
 *  attached file (`AM-121`, on by default); where an administrator has switched that off
 *  it is refused, and the text comes back to the box. */
const QUESTION_LIMIT = 2000;

/** Within this distance of the end the reader is "at the latest", and a new answer
 *  follows them; further up, they are reading, and nothing moves under them. */
const AT_END_PX = 80;

/** On a phone the rail is a drawer over the conversation: choosing where to go closes
 *  it, or the chat just chosen sat under half a screen of chat names. Same breakpoint as
 *  the CSS that makes it a drawer. */
function closeDrawer(rail: HTMLDetailsElement | null) {
  if (rail?.open && window.matchMedia("(max-width: 860px)").matches) rail.open = false;
}

/** The conversation's title: the reader's own name for it, else the first thing they
 *  actually asked. */
function chatTitle(conversation: ConversationSummary): string {
  return conversation.title?.trim() || conversation.first_question?.trim() || "New chat";
}

/** The model picked in the composer, kept for this browser session (`AM-116`). */
const MODEL_KEY = "legalmind.ask.model";

/** What the server says when a model is listed but cannot be served — said here too,
 *  so a chat is not created for a question nobody can answer. */
function notConfigured(model: AskModel): string {
  return `${model.label} is not configured yet. Choose Gemini to ask this question.`;
}

/** A rename in progress. In a ref as well as state: Escape and Enter must not be undone
 *  by the blur that follows when the field leaves the page. */
interface Rename {
  id: string;
  draft: string;
  error: string | null;
  saving: boolean;
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
      exact_text_requested: result.exact_text_requested ?? false,
      sources: result.sources ?? [],
      answered_by: result.answered_by ?? null,
      latency_ms: result.latency_ms ?? null,
    },
  ];
}

interface Scope {
  contractId: string | null;
  documentName: string | null;
}

export function AskWorkspace() {
  const { can } = useSession();
  const router = useRouter();
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
  /** The question that failed, so "Try again" can send it again. */
  const [failed, setFailed] = useState<string | null>(null);
  /** One atomic status line for a screen reader when an answer arrives. */
  const [announce, setAnnounce] = useState("");
  const [materialTick, setMaterialTick] = useState(0);
  /** The composer's model list and choice (`AM-116`). An empty list (it failed to
   *  load) hides the control and the question goes to the server's default. */
  const [models, setModels] = useState<AskModel[]>([]);
  const [model, setModel] = useState("gemini");
  const [rename, setRenameState] = useState<Rename | null>(null);
  const renameRef = useRef<Rename | null>(null);
  const [deleting, setDeleting] = useState<ConversationSummary | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState<unknown>(null);

  const railRef = useRef<HTMLDetailsElement>(null);
  const logRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  /** The chat on screen now — read after an await, when the render's `activeId` is
   *  stale: an answer belongs to the chat it was asked in, not the one open later. */
  const activeRef = useRef(activeId);
  activeRef.current = activeId;
  /** The chat whose address this page just set itself; its turns are already here. */
  const selfAddressedRef = useRef<string | null>(null);
  /** A chat created by an ask that then failed — reused by the retry, not orphaned —
   *  with the chat it was asked FROM, so it is reused only from there. It holds the
   *  uploaded document too: the retry has no file left to upload. */
  const createdRef = useRef<{ from: string | null; id: string } | null>(null);
  /** Bumped by New chat: an answer still arriving for the cleared chat is not shown. */
  const epochRef = useRef(0);
  /** Whether the reader is at the end of the conversation (`AT_END_PX`). A ref for the
   *  scroll logic and a boolean state for the "Jump to latest" control — never the scroll
   *  position itself, which would re-render the page on every scroll frame. */
  const atEndRef = useRef(true);
  const [awayFromEnd, setAwayFromEnd] = useState(false);
  /** An answer arrived while the reader was further up: said on the jump control. */
  const [unseen, setUnseen] = useState(false);
  /** Where the next change of `turns` scrolls: the end of a chat just opened, or the
   *  start of an answer that has just arrived — set by whoever sets the turns. */
  const anchorRef = useRef<"end" | "answer" | null>(null);
  const busy = pending !== null;
  const answerShown = useQuickClose(activeId);

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

  useEffect(() => {
    if (!canAsk) return;
    try {
      const saved = window.sessionStorage.getItem(MODEL_KEY);
      if (saved) setModel(saved);
    } catch {
      // No session storage (a private window): the default stands.
    }
    api.askModels().then(setModels, () => setModels([]));
  }, [canAsk]);

  function chooseModel(id: string) {
    setModel(id);
    setError(null);
    try {
      window.sessionStorage.setItem(MODEL_KEY, id);
    } catch {
      // Kept for this page only.
    }
  }

  /** Back to an empty chat: New chat, and deleting the chat that is open. */
  function resetChat() {
    closeDrawer(railRef.current);
    setTurns([]);
    setAttachment(null);
    setScope({ contractId: null, documentName: null });
    setVersionId(null);
    setQuestion("");
    setError(null);
    setFailed(null);
    createdRef.current = null;
    epochRef.current += 1;
  }

  function setRename(next: Rename | null) {
    renameRef.current = next;
    setRenameState(next);
  }

  /** Saves the name, or keeps the old one when the field is empty or unchanged. The
   *  server is the authority on what a name may be; its refusal stays at the field. */
  async function saveRename() {
    const current = renameRef.current;
    if (!current || current.saving) return;
    const title = current.draft.replace(/\s+/g, " ").trim();
    const before = conversations?.find((c) => c.id === current.id);
    if (!title || !before || title === chatTitle(before)) {
      setRename(null);
      return;
    }
    setRename({ ...current, saving: true, error: null });
    // Another chat's rename may have opened meanwhile; this one only closes itself.
    const mine = () => renameRef.current?.id === current.id;
    try {
      const saved = await api.renameConversation(current.id, title);
      setConversations((list) =>
        list?.map((c) => (c.id === current.id ? { ...c, title: saved.title } : c)) ?? list);
      if (mine()) setRename(null);
    } catch (cause) {
      if (mine()) setRename({
        ...current,
        saving: false,
        error: cause instanceof ApiError && cause.status === 422
          ? "Use a name of up to 120 characters, on one line."
          : describeError(cause),
      });
    }
  }

  async function confirmDelete() {
    const target = deleting;
    if (!target || deleteBusy) return;
    setDeleteBusy(true);
    setDeleteError(null);
    try {
      await api.deleteConversation(target.id);
    } catch (cause) {
      // Already gone (another tab deleted it): the outcome the reader asked for.
      if (!(cause instanceof ApiError && cause.isNotFound)) {
        setDeleteError(cause);
        setDeleteBusy(false);
        return;
      }
    }
    setConversations((list) => list?.filter((c) => c.id !== target.id) ?? list);
    setDeleting(null);
    setDeleteBusy(false);
    setAnnounce("Chat deleted.");
    if (target.id === activeRef.current || target.id === createdRef.current?.id) {
      resetChat();
      router.replace("/dashboard/ask");
    }
  }

  // The open conversation, replayed with the citations it carried live
  // (`AM-25` r5). `?id=` is the only selector — so a chat is a shareable URL.
  useEffect(() => {
    // The first answer gave this chat its address; the turns are already on screen,
    // and refetching them flashed the skeleton and dropped the live comparison.
    if (activeId && activeId === selfAddressedRef.current) {
      selfAddressedRef.current = null;
      return;
    }
    let cancelled = false;
    closeDrawer(railRef.current);
    setUnseen(false);
    setNotFound(false);
    setError(null);
    setFailed(null);
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
        anchorRef.current = "end";
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

  /* Scrolling the LOG, never the page: a long answer must not move the rail or the
   * composer. Until 2026-10-06 every change went to the very bottom — so a long answer
   * opened on its Sources legend with its first lines out of view, and a reader who had
   * scrolled up to re-read an earlier answer was pulled down mid-sentence when the new
   * one arrived. Now: a chat opens at its end; a question just sent is shown; an answer
   * opens at its own start (its question at the top) if the reader was following, and
   * otherwise moves nothing and says "New answer below". */
  useEffect(() => {
    const node = logRef.current;
    if (!node) return;
    const onScroll = () => {
      const atEnd = node.scrollHeight - node.scrollTop - node.clientHeight < AT_END_PX;
      atEndRef.current = atEnd;
      setAwayFromEnd(!atEnd);
      if (atEnd) setUnseen(false);
    };
    node.addEventListener("scroll", onScroll, { passive: true });
    return () => node.removeEventListener("scroll", onScroll);
  }, []);

  useLayoutEffect(() => {
    const node = logRef.current;
    const anchor = anchorRef.current;
    anchorRef.current = null;
    if (!node || !anchor) return;
    const asked = anchor === "answer"
      ? [...node.querySelectorAll<HTMLElement>(".ws-turn--user")].at(-1)
      : undefined;
    node.scrollTop = asked
      ? node.scrollTop + asked.getBoundingClientRect().top - node.getBoundingClientRect().top - 12
      : node.scrollHeight;
  }, [turns]);

  // The reader just sent: their question and the progress line are what they look at.
  // An error lands at the end too, and is followed only if the reader is there.
  useLayoutEffect(() => {
    const node = logRef.current;
    if (node && (pending !== null || (error && atEndRef.current))) {
      node.scrollTop = node.scrollHeight;
    }
  }, [pending, error]);

  function jumpToEnd() {
    const node = logRef.current;
    if (!node) return;
    node.scrollTo({ top: node.scrollHeight, behavior: scrollMotion() });
    setUnseen(false);
    // The control disappears at the end; focus goes to the conversation it scrolled,
    // not to the page.
    node.focus({ preventScroll: true });
  }

  /* The composer is disabled while an answer is found, which drops focus to the
   * page; once it is enabled again (after that render, not before — a disabled
   * textarea cannot take focus) it gets it back, unless the reader moved on. */
  const wasBusy = useRef(false);
  useEffect(() => {
    if (wasBusy.current && !busy && (document.activeElement === document.body
                                     || document.activeElement === null)) {
      inputRef.current?.focus();
    }
    wasBusy.current = busy;
  }, [busy]);

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

  const submit = useCallback(async (again?: string) => {
    const typed = again ?? question;
    const asked = typed.trim();
    if (!asked || busy) return;
    const chosen = models.find((m) => m.id === model);
    if (chosen && !chosen.configured) {
      // The question stays in the box; choosing Gemini and sending again works.
      setError(notConfigured(chosen));
      return;
    }
    const askedIn = activeId;
    const epoch = epochRef.current;
    const stale = () => activeRef.current !== askedIn || epochRef.current !== epoch;
    setPending(asked);
    // The box empties for the question being sent. "Try again" resends an earlier one,
    // so it empties the box only when that is what the box holds — the composer stays
    // editable while an answer is found, and the next question may already be there.
    setQuestion((current) => (again === undefined || current.trim() === asked ? "" : current));
    setError(null);
    setFailed(null);
    setAnnounce("");
    const file = attachment;
    const abort = new AbortController();
    const timer = window.setTimeout(() => abort.abort(), ASK_TIMEOUT_MS);
    try {
      const created = createdRef.current?.from === askedIn ? createdRef.current : null;
      let conversationId = created?.id ?? activeId;
      let contractId = scope.contractId;

      if (file && conversationId && scope.contractId !== null) {
        // D6: a chat that already has a document keeps it, and the further file is
        // the chat's material beside it — named in every answer drawn from it. Earlier
        // citations keep the first document's reading order, which never moves.
        await api.addAttachment(conversationId, file);
        setAttachment(null);
        setMaterialTick((n) => n + 1);
      } else if (file) {
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
          // No chat yet: the document starts one.
          conversationId = (await api.createConversation(contract.id)).id;
          createdRef.current = { from: askedIn, id: conversationId };
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
        conversationId = (await api.createConversation(null)).id;
        createdRef.current = { from: askedIn, id: conversationId };
      }

      const result = await api.ask(conversationId, asked, versionId ?? undefined,
                                   undefined, abort.signal, chosen?.id);
      createdRef.current = null;
      void loadConversations();
      // The reader moved to another chat while this was answered: it is kept in
      // its own chat (the rail shows it) and never appended to the one on screen.
      if (stale()) return;
      if (atEndRef.current) anchorRef.current = "answer";
      else setUnseen(true);
      setTurns((previous) => [...previous, ...liveTurns(asked, result)]);
      if (result.answer_state === "ANSWERED") answerShown(result.message_id, conversationId);
      setMaterialTick((n) => n + 1);
      if (result.comparison?.review_id) setReviewId(result.comparison.review_id);
      setAnnounce(result.answer_state === "ANSWERED"
        ? "LegalMind answered."
        : "LegalMind could not answer this from the approved material.");
      if (conversationId !== activeId) {
        // The URL becomes the conversation's address without a navigation; the
        // effect that follows is told these turns are already here.
        selfAddressedRef.current = conversationId;
        const url = new URL(window.location.href);
        url.searchParams.set("id", conversationId);
        window.history.replaceState(null, "", url);
      }
    } catch (cause) {
      if (stale()) return;
      setFailed(asked);
      // The reader's words come back to the box to edit, exactly as typed — a refusal
      // for length is answered by shortening the text, which "Try again" alone cannot
      // do. Not over anything they typed since.
      setQuestion((current) => (current.trim() ? current : typed));
      setError(abort.signal.aborted
        ? "The answer took too long to arrive. Your question is kept — try again."
        : cause);
    } finally {
      window.clearTimeout(timer);
      setPending(null);
    }
  }, [activeId, attachment, busy, can, loadConversations, model, models, question,
      scope.contractId, versionId]);

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
  /** The counter appears near the cap, not from the first keystroke. */
  const nearLimit = question.length > QUESTION_LIMIT * 0.9;

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
            onClick={resetChat}
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
                    {group.items.map((conversation) => rename?.id === conversation.id ? (
                      <li key={conversation.id} className="ws-chat__rename">
                        <label className="ws-visually-hidden" htmlFor="ws-chat-rename">
                          Chat name
                        </label>
                        <input
                          id="ws-chat-rename"
                          autoFocus
                          value={rename.draft}
                          maxLength={120}
                          disabled={rename.saving}
                          aria-invalid={rename.error ? true : undefined}
                          aria-describedby={rename.error ? "ws-chat-rename-error" : undefined}
                          onFocus={(event) => event.currentTarget.select()}
                          onChange={(event) =>
                            setRename({ ...rename, draft: event.target.value, error: null })}
                          onKeyDown={(event) => {
                            if (event.key === "Enter" && !isImeEnter(event)) {
                              event.preventDefault();
                              void saveRename();
                            } else if (event.key === "Escape") {
                              event.preventDefault();
                              setRename(null);
                            }
                          }}
                          onBlur={() => void saveRename()}
                        />
                        {rename.error ? (
                          <p id="ws-chat-rename-error" className="ws-chat__renameerror" role="alert">
                            {rename.error}
                          </p>
                        ) : null}
                      </li>
                    ) : (
                      <li key={conversation.id} className="ws-chat__railrow">
                        <Link
                          className="ws-chat__railitem"
                          href={`/dashboard/ask?id=${conversation.id}`}
                          aria-current={conversation.id === activeId ? "page" : undefined}
                          /* the whole name, for a title the rail cuts short */
                          title={chatTitle(conversation)}
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
                        <span className="ws-chat__railacts">
                          <button
                            type="button"
                            aria-label={`Rename chat: ${chatTitle(conversation)}`}
                            title="Rename"
                            onClick={() => setRename({
                              id: conversation.id, draft: chatTitle(conversation),
                              error: null, saving: false,
                            })}
                          >
                            <IconPencil size={14} />
                          </button>
                          <button
                            type="button"
                            data-destructive=""
                            aria-label={`Delete chat: ${chatTitle(conversation)}`}
                            title="Delete"
                            onClick={() => {
                              setDeleteError(null);
                              setDeleting(conversation);
                            }}
                          >
                            <IconTrash size={14} />
                          </button>
                        </span>
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
          {/* The question is the conversation's first turn and the rail's title; a
              third copy as a page headline was the same words read three times
              (owner, 2026-09-28). The heading stays for the document outline and a
              screen reader; the visible header is the scope alone. */}
          <h1 className="ws-visually-hidden">
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
                standards and the approved statutes. Attach a document to ask about one.
              </>
            )}
          </p>
        </header>

        {/* A tab stop: a conversation of refusals holds no link or button, and a region
            that scrolls must be reachable by keyboard to be scrolled by one (WCAG 2.1.1). */}
        <div className="ws-chat__log" ref={logRef} tabIndex={0} role="region"
             aria-label="Messages">
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
                  {[...OPENERS, scope.contractId ? DOCUMENT_OPENER : KNOWLEDGE_OPENER]
                    .map((opener) => (
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
                    <span className="ws-ask__role ws-visually-hidden">You</span> {pending}
                  </p>
                </div>
                <div className="ws-turn ws-turn--ai">
                  <AiVoice />
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
                {failed ? (
                  <button
                    type="button"
                    className="ws-btn ws-btn--sm"
                    onClick={() => void submit(failed)}
                  >
                    Try again
                  </button>
                ) : null}
              </div>
            ) : null}
            <p className="ws-visually-hidden" role="status" aria-atomic="true">
              {announce}
            </p>
          </div>
        </div>

        {/* Back to the latest turn, when the reader has scrolled away from it. Outside
            the scrolling log, so it stays put while the conversation moves under it. */}
        <div className="ws-chat__jumpbar">
          {awayFromEnd && (turns.length > 0 || busy) ? (
            <button type="button" className="ws-chat__jump" onClick={jumpToEnd}>
              <IconChevronDown size={15} />
              {unseen ? "New answer below" : "Jump to latest"}
            </button>
          ) : null}
        </div>

        {/* ---- composer --------------------------------------------------- */}
        <form
          className="ws-chat__composer"
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
          }}
        >
          <ChatMaterial conversationId={activeId} refresh={materialTick} />
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
                  : "This file is added to the chat beside its document. Answers name each file."}
              </span>
            </div>
          ) : null}

          <div className="ws-chat__inputrow">
            {canUpload ? (
              <>
                {/* Not a tab stop and not in the tree: "Add files" below is the one
                    named control; this unnamed twin was a second, silent stop (AM-109). */}
                <input
                  ref={fileRef}
                  className="ws-visually-hidden"
                  tabIndex={-1}
                  aria-hidden="true"
                  type="file"
                  accept=".pdf,.docx,.md,.txt"
                  onChange={(event) => {
                    chooseFile(event.target.files?.[0] ?? null);
                    event.target.value = "";
                  }}
                />
                <button
                  type="button"
                  className="ws-chat__attach"
                  // Below 640px the label is hidden to give the question the
                  // width, so the accessible name has to come from here:
                  // `display: none` removes text from the accessibility tree,
                  // and an unnamed button is a dead end for a screen reader.
                  aria-label="Add files"
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
              placeholder="Ask LegalMind…"
              aria-describedby={nearLimit ? "ws-chat-count" : undefined}
              /* Editable while an answer is found (it was disabled, which locked the
                 reader out for the 9–18 s an answer takes and dropped their focus);
                 sending stays one at a time — the button and `submit` both hold it.
                 No `maxLength`: it cut a pasted email at 2,000 characters without a
                 word, and the answer was then about a text nobody wrote. */
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={(event) => {
                // Enter sends, Shift+Enter breaks the line — the composer
                // convention. A textarea is what lets a long question be read
                // back before it is sent. Enter inside an IME composition picks the
                // composed word and sends nothing.
                if (event.key === "Enter" && !event.shiftKey && !isImeEnter(event)) {
                  event.preventDefault();
                  void submit();
                }
              }}
            />
            <ModelPicker models={models} value={model} disabled={busy} onChange={chooseModel} />
            <button
              className="ws-chat__send"
              type="submit"
              aria-label={busy ? "Searching…" : "Send question"}
              disabled={busy || !question.trim()}
            >
              <IconSend size={16} />
            </button>
          </div>
          {nearLimit ? (
            <p id="ws-chat-count" className="ws-chat__count"
               data-over={question.length > QUESTION_LIMIT ? "" : undefined}>
              {question.length > QUESTION_LIMIT
                ? `${question.length.toLocaleString("en-IN")} characters — kept as your material, like an attached file.`
                : `${question.length.toLocaleString("en-IN")} / ${QUESTION_LIMIT.toLocaleString("en-IN")} characters`}
            </p>
          ) : null}
          <p className="ws-chat__note">
            Answers cite the material they came from, or say they cannot. Verify against the
            original document.
          </p>
        </form>
      </section>

      {deleting ? (
        <Dialog onClose={() => { if (!deleteBusy) setDeleting(null); }} titleId="ws-chat-delete-title">
          <h2 id="ws-chat-delete-title">Delete this chat?</h2>
          <p className="ws-modal__body"><strong>{chatTitle(deleting)}</strong></p>
          <p className="ws-modal__body">
            Its questions and answers are deleted permanently. This cannot be undone.
          </p>
          {deleteError ? (
            <p className="ws-field__error" role="alert">{describeError(deleteError)}</p>
          ) : null}
          <div className="ws-modal__acts">
            <button type="button" className="ws-btn" disabled={deleteBusy}
                    onClick={() => setDeleting(null)}>
              Cancel
            </button>
            <button type="button" className="ws-btn ws-btn--bad" disabled={deleteBusy}
                    onClick={() => void confirmDelete()}>
              {deleteBusy ? "Deleting…" : "Delete chat"}
            </button>
          </div>
        </Dialog>
      ) : null}
    </div>
  );
}
