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
 * Attaching a file (`AM-133`)
 * ---------------------------
 * Ask is a chat assistant, and a review is the Dashboard's job: a file attached
 * here is this chat's material — read, quoted and named in the answers drawn from
 * it, and never a Contract, never analysed, never on the Dashboard (`AM-110` r3).
 * A question whether a document meets our standards is answered by the server's
 * fixed reply, which says to upload it on the Dashboard (`AM-25` r4).
 *
 * A chat that already has a contract (made before `AM-133`, or opened from a
 * document) keeps it, its citations and its Findings table.
 */

import { AssistantRuntimeProvider, useAuiState } from "@assistant-ui/react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { Dialog } from "@/components/Dialog";
import { Thread } from "@/components/ui/thread";
import { ASK_TIMEOUT_MS, ApiError, api, describeError } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { AskModel, AskResult, ConversationSummary, ConversationTurn } from "@/lib/types";

import {
  IconChevronUp,
  IconFile,
  IconMessage,
  IconMore,
  IconPanel,
  IconPencil,
  IconPlus,
  IconSearch,
  IconSignOut,
  IconTrash,
  IconX,
} from "./icons";
import { ChatMaterial } from "./ChatMaterial";
import { ModelPicker } from "./ModelPicker";
import { AiVoice, TranscriptTurn, useQuickClose } from "./TranscriptTurn";
import { Avatar } from "./WorkspaceShell";
import {
  STOPPED, arrived, before, chatTitle, enterSends, isImeEnter, liveTurns, useAskRuntime,
  useFocusAfterAnswer, waitEnded,
} from "./askThread";

/** Mirrors the server's material limit (`LEGALMIND_ASK_ATTACHMENT_MAX_BYTES`) — a
 *  friendly message before a 10 MB round trip. The server stays the authority. */
const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
const SUPPORTED_EXTENSIONS = [".pdf", ".docx", ".md", ".txt"];

function preflightProblem(file: File): string | null {
  const name = file.name.toLowerCase();
  if (!SUPPORTED_EXTENSIONS.some((extension) => name.endsWith(extension))) {
    return "Only PDF, Word (.docx), Markdown and text files can be attached.";
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    return "That file is larger than 10 MB.";
  }
  if (file.size === 0) return "That file is empty.";
  return null;
}

/** Openers, as editable drafts — nothing sends until the reader sends it. The
 *  fourth fits the chat: a comparison only in a chat that has a contract. */
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

/** The typed question's own cap, the server's (`attachments.QUESTION_MAX_CHARS`). Longer
 *  text is never cut here: the server keeps it as the chat's material, exactly as an
 *  attached file (`AM-121`, on by default); where an administrator has switched that off
 *  it is refused, and the text comes back to the box. */
const QUESTION_LIMIT = 5000;

/** On a phone the rail is a drawer over the conversation: choosing where to go closes
 *  it, or the chat just chosen sat under half a screen of chat names. Same breakpoint as
 *  the CSS that makes it a drawer. */
function closeDrawer(rail: HTMLDetailsElement | null) {
  if (rail?.open && window.matchMedia("(max-width: 860px)").matches) rail.open = false;
}

/** Shown in the picker until `GET /ask/models` names the server's own default. */
const FALLBACK_MODEL = "gemini";

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

interface Scope {
  contractId: string | null;
  documentName: string | null;
}

/** The character count, read from the composer's own text. Always in the page and
 *  empty-and-hidden below the threshold, so the input's `aria-describedby` never
 *  points at nothing. */
function QuestionCount() {
  const length = useAuiState((s) => s.composer.text.length);
  if (length <= QUESTION_LIMIT * 0.9) return <span id="ws-chat-count" hidden />;
  return (
    <p id="ws-chat-count" className="ws-chat__count"
       data-over={length > QUESTION_LIMIT ? "" : undefined}>
      {length > QUESTION_LIMIT
        ? `${length.toLocaleString("en-IN")} characters — kept as your material, like an attached file.`
        : `${length.toLocaleString("en-IN")} / ${QUESTION_LIMIT.toLocaleString("en-IN")} characters`}
    </p>
  );
}

export function AskWorkspace() {
  const { can, identity, signOut } = useSession();
  const router = useRouter();
  const activeId = useSearchParams().get("id");

  const [conversations, setConversations] = useState<ConversationSummary[] | null>(null);
  const [turns, setTurns] = useState<ConversationTurn[]>([]);
  const [scope, setScope] = useState<Scope>({ contractId: null, documentName: null });
  const [loadingChat, setLoadingChat] = useState(false);
  const [notFound, setNotFound] = useState(false);
  /** The question being answered, with the chat and New-chat epoch it was asked in. */
  const [pending, setPending] = useState<
    { text: string; chat: string | null; epoch: number; editOf?: string | undefined } | null>(null);
  const [attachment, setAttachment] = useState<File | null>(null);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<unknown>(null);
  /** The Review whose Findings answer a routed comparison turn. */
  const [reviewId, setReviewId] = useState<string | null>(null);
  /** The question that failed, so "Try again" can send it again. */
  const [failed, setFailed] = useState<{ text: string; editOf?: string | undefined } | null>(null);
  /** One atomic status line for a screen reader when an answer arrives. */
  const [announce, setAnnounce] = useState("");
  const [materialTick, setMaterialTick] = useState(0);
  /** The composer's model list and choice (`AM-116`). An empty list (it failed to
   *  load) hides the control and the question goes to the server's default. The
   *  choice is the CHAT's (`AM-122`): it is read from the chat when one is opened,
   *  stored on the server when the reader changes it, and a new chat starts on the
   *  default — never on another chat's choice, and never on this tab's memory.
   *  `null` is "never chosen": no model is sent and the server's default answers,
   *  so a chat is pinned only by the reader's own choice. */
  const [models, setModels] = useState<AskModel[]>([]);
  const [model, setModel] = useState<string | null>(null);
  const shownModel = model ?? models.find((m) => m.default)?.id ?? FALLBACK_MODEL;
  const savingModel = useRef<Promise<void>>(Promise.resolve());
  const [rename, setRenameState] = useState<Rename | null>(null);
  const renameRef = useRef<Rename | null>(null);
  const [deleting, setDeleting] = useState<ConversationSummary | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState<unknown>(null);
  /** The sidebar hidden by its own toggle, on a wide screen (a phone has the drawer). */
  const [railHidden, setRailHidden] = useState(false);
  /** The one open menu: a chat's "…" (in the sidebar or the top bar), or the account's. */
  const [menuFor, setMenuFor] = useState<
    { id: string; at: "rail" | "head" | "account"; up?: boolean } | null>(null);

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
  /** The ask in flight, so Stop can abandon it. */
  const abortRef = useRef<AbortController | null>(null);
  /** One answer at a time, from any chat; it is SHOWN only in the chat it was asked in,
   *  so opening another chat mid-answer shows that chat, not this question and its Stop. */
  const busy = pending !== null;
  const shownPending = pending && pending.chat === activeId && pending.epoch === epochRef.current
    ? pending.text : null;
  const answerShown = useQuickClose(activeId);

  const canAsk = can(P.ASSIST_ASK);
  // Material needs only Ask (`AM-110`): attaching here creates no contract.
  const canUpload = canAsk;

  const loadConversations = useCallback(async () => {
    try {
      const { items } = await api.conversations({ page_size: 50, has_document: "false" });
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
    if (canAsk) api.askModels().then(setModels, () => setModels([]));
  }, [canAsk]);

  /** The reader's choice becomes the open chat's at once, so the next turn — from
   *  this tab or any other — goes to it. A chat not yet created takes the choice
   *  with its first question. The server refuses a model it cannot serve BY NAME,
   *  and the composer says so instead of letting the choice look made. */
  function chooseModel(id: string) {
    setModel(id);
    setError(null);
    const chat = activeRef.current;
    if (!chat) return;
    // One save after another, in the order chosen: two quick switches sent together can
    // reach the server the other way round and leave the chat on the earlier choice.
    savingModel.current = savingModel.current
      .then(() => api.updateConversation(chat, { model: id }))
      .then(() => undefined, (cause) => {
        if (activeRef.current === chat) setError(cause);
      });
  }

  /** Back to an empty chat: New chat, and deleting the chat that is open. */
  function resetChat() {
    closeDrawer(railRef.current);
    setTurns([]);
    setAttachment(null);
    setScope({ contractId: null, documentName: null });
    setModel(null);
    runtime.thread.composer.setText("");
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
      const saved = await api.updateConversation(current.id, { title });
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
      // The "…" that opened the dialog went with the chat; after the dialog's own focus
      // return, the reader lands in the new chat's box rather than on the page.
      requestAnimationFrame(() => inputRef.current?.focus());
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
    setNotFound(false);
    setError(null);
    setFailed(null);
    setReviewId(null);
    if (!activeId) {
      setTurns([]);
      setScope({ contractId: null, documentName: null });
      setModel(null);
      return;
    }
    // Emptied first, so the viewport sees the chat arrive and opens it at its end;
    // the previous chat's turns never sit under the loading skeleton.
    setTurns([]);
    setLoadingChat(true);
    (async () => {
      try {
        const detail = await api.conversation(activeId);
        if (cancelled) return;
        setTurns(detail.messages);
        // The chat's own model, or the default: the composer shows what the next
        // turn will actually go to (`AM-122`).
        setModel(detail.model ?? null);
        let documentName: string | null = null;
        if (detail.contract_id) {
          try {
            const contract = await api.contract(detail.contract_id);
            documentName = contract.name;
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

  // Each sidebar toggle hides itself, so it hands focus to the other one.
  const railToggledRef = useRef(false);
  useEffect(() => {
    if (!railToggledRef.current) return;
    railToggledRef.current = false;
    document.querySelector<HTMLElement>(
      railHidden ? ".ws-chat__head .ws-chat__collapse" : ".ws-chat__brand .ws-chat__collapse")?.focus();
  }, [railHidden]);

  // A menu takes focus on its first item; Escape hands it back to the toggle, and a
  // click anywhere else closes it.
  useEffect(() => {
    if (!menuFor) return;
    document.querySelector<HTMLElement>(".ws-chat__menu button")?.focus();
    const away = (event: Event) => {
      if (event instanceof KeyboardEvent) {
        if (event.key !== "Escape") return;
        document.querySelector<HTMLElement>(".ws-chat__menuwrap [aria-expanded='true']")?.focus();
        setMenuFor(null);
        return;
      }
      // A click elsewhere, or focus tabbing out of the open menu and its toggle.
      const target = event.target as Element | null;
      if (!target?.closest?.(".ws-chat__menuwrap:has([aria-expanded='true'])")) {
        setMenuFor(null);
      }
    };
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", away);
    document.addEventListener("focusin", away);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", away);
      document.removeEventListener("focusin", away);
    };
  }, [menuFor]);

  /* The rail is a native <details>: open on a desktop, closed on a phone, where
   * it is a drawer and would otherwise cost half the screen before a single
   * word is read. Set once, imperatively, because `open` is the element's own
   * state from then on — the reader's toggle must not be overridden on every
   * render. Matches the CSS breakpoint that turns the summary into a control. */
  useEffect(() => {
    const rail = railRef.current;
    if (rail) rail.open = !window.matchMedia("(max-width: 860px)").matches;
  }, []);

  /* Scrolling is the assistant-ui viewport's (`turnAnchor="top"`), and keeps the rules
   * set on 2026-10-06: the LOG scrolls, never the page; a chat opens at its end; a
   * question just sent is shown; an answer opens at its own start, question at the top;
   * and a reader who scrolled up is not moved — "New answer below" says it arrived. */
  function focusLog() {
    // The jump control disappears at the end; focus goes to the conversation it
    // scrolled, not to the page.
    logRef.current?.focus({ preventScroll: true });
  }

  useFocusAfterAnswer(busy, inputRef);

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

  /** The reader's words back in the box, exactly as typed — never over anything they
   *  typed since. The composer empties itself on send, so a question that was not
   *  answered has to be put back. */
  function restoreQuestion(typed: string) {
    const composer = runtime.thread.composer;
    if (!composer.getState().text.trim()) composer.setText(typed);
  }

  /** Every send — the composer's (through the runtime's `onNew`), an edit of one of the
   *  reader's questions (`onEdit`, `AM-134`) and "Try again". */
  async function submit(typed: string, editOf?: string) {
    const asked = typed.trim();
    if (!asked || busy) return;
    const chosen = models.find((m) => m.id === shownModel);
    if (chosen && !chosen.configured) {
      // The question stays in the box; choosing Gemini and sending again works.
      restoreQuestion(typed);
      setError(notConfigured(chosen));
      return;
    }
    const askedIn = activeId;
    const epoch = epochRef.current;
    const stale = () => activeRef.current !== askedIn || epochRef.current !== epoch;
    // A keyboard Send is replaced by Stop as the answer starts; focus goes to the box,
    // not to the page.
    if (document.activeElement?.closest(
      "[data-slot='aui_composer-shell'], [data-slot='aui_edit-composer']")) {
      inputRef.current?.focus();
    }
    setPending({ text: asked, chat: askedIn, epoch, editOf });
    // "Try again" resends an earlier question, so it empties the box only when that is
    // what the box holds — the composer stays editable while an answer is found, and
    // the next question may already be there.
    const composer = runtime.thread.composer;
    if (composer.getState().text.trim() === asked) composer.setText("");
    setError(null);
    setFailed(null);
    setAnnounce("");
    const file = attachment;
    const abort = new AbortController();
    abortRef.current = abort;
    const timer = window.setTimeout(() => abort.abort(), ASK_TIMEOUT_MS);
    try {
      const created = createdRef.current?.from === askedIn ? createdRef.current : null;
      let conversationId = created?.id ?? activeId;
      if (!conversationId) {
        conversationId = (await api.createConversation(null)).id;
        createdRef.current = { from: askedIn, id: conversationId };
      }
      if (file) {
        // The chat's material (`AM-133`): read and quoted in this chat, never a
        // contract. Saved before the question, so this very answer can read it; a
        // retry finds it already here and sends only the question.
        await api.addAttachment(conversationId, file);
        setAttachment(null);
        setMaterialTick((n) => n + 1);
      }

      // No document version is named here: the Ask page has no version open, so
      // the server's own rule — the newest version of THIS chat's document — is
      // what the reader means. Naming one from page state is how a version of a
      // different contract reached a chat it did not belong to (a reader's upload
      // after switching chats, 2026-10-07): the dock, which has a version open,
      // still names it.
      // Stop during an upload lands here: the file and its chat are kept whole (an
      // upload cannot be taken back halfway), and the question is not sent.
      abort.signal.throwIfAborted();
      const result = await api.ask(conversationId, asked, undefined,
                                   undefined, abort.signal, model ?? undefined, editOf);
      createdRef.current = null;
      void loadConversations();
      // The reader moved to another chat while this was answered: it is kept in
      // its own chat (the rail shows it) and never appended to the one on screen.
      if (stale()) return;
      setTurns((previous) => [...before(previous, editOf), ...liveTurns(asked, result)]);
      if (result.answer_state === "ANSWERED") answerShown(result.message_id, conversationId);
      setMaterialTick((n) => n + 1);
      if (result.comparison?.review_id) setReviewId(result.comparison.review_id);
      setAnnounce(arrived(result));
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
      // An edit whose question is gone (replaced by an earlier attempt) is offered
      // again as a plain question; any other failed edit is re-read from the server,
      // rather than guessed — except after Stop or a timeout, when the server may still
      // be replacing the turns and an early read would show them as they were.
      const gone = cause instanceof ApiError && cause.isNotFound;
      setFailed({ text: asked, editOf: gone ? undefined : editOf });
      if (editOf && activeId && !abort.signal.aborted) {
        api.conversation(activeId).then((detail) => {
          if (!stale()) setTurns(detail.messages);
        }, () => undefined);
      }
      // The reader's words come back to the box to edit, exactly as typed — a refusal
      // for length is answered by shortening the text, which "Try again" alone cannot
      // do. Not over anything they typed since, and not an edit's: sent from the box it
      // would be a new question, not the edit; "Try again" repeats the edit.
      if (!editOf) restoreQuestion(typed);
      setError(abort.signal.aborted ? waitEnded(abort.signal.reason) : cause);
    } finally {
      window.clearTimeout(timer);
      abortRef.current = null;
      setPending(null);
    }
  }

  const runtime = useAskRuntime({
    turns, busy, send: submit, stop: () => abortRef.current?.abort(STOPPED),
    pending: shownPending === null ? null : { text: shownPending, editOf: pending?.editOf },
  });

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

  const activeChat = conversations?.find((c) => c.id === activeId) ?? null;
  const accountOpen = menuFor?.at === "account";

  /** A chat's "…" — Rename and Delete, as the starter's thread list has them. A
   *  disclosure (a button that shows two buttons), not an ARIA menu: Tab and Enter are
   *  all it needs, and a `role="menu"` would promise arrow keys it does not have. */
  function chatMenu(conversation: ConversationSummary, at: "rail" | "head") {
    const open = menuFor?.id === conversation.id && menuFor.at === at;
    const name = chatTitle(conversation);
    return (
      <span className="ws-chat__menuwrap">
        <button type="button" className="ws-chat__iconbtn ws-chat__more"
                aria-label={`More options: ${name}`} title="More options" aria-expanded={open}
                onClick={(event) => {
                  // Near the bottom of the chat list the options open upward, or the
                  // list's own scroll would clip them.
                  const list = event.currentTarget.closest(".ws-chat__railbody");
                  const up = !!list && list.getBoundingClientRect().bottom
                    - event.currentTarget.getBoundingClientRect().bottom < 96;
                  setMenuFor(open ? null : { id: conversation.id, at, up });
                }}>
          <IconMore size={16} />
        </button>
        {open ? (
          <span className="ws-menu__list ws-chat__menu" data-up={menuFor?.up ? "" : undefined}>
            <button type="button" className="ws-menu__item"
                    aria-label={`Rename chat: ${name}`}
                    onClick={() => {
                      setMenuFor(null);
                      // The name is edited in the sidebar's row, so that row must be on
                      // screen: the sidebar shown, the phone's drawer open, the search clear.
                      setRailHidden(false);
                      setSearch("");
                      if (railRef.current) railRef.current.open = true;
                      setRename({ id: conversation.id, draft: name, error: null, saving: false });
                    }}>
              <IconPencil size={14} /> Rename
            </button>
            <button type="button" className="ws-menu__item"
                    data-destructive="" aria-label={`Delete chat: ${name}`}
                    onClick={(event) => {
                      // The dialog hands focus back to what had it; the "…" outlives this
                      // button, which closes with the options.
                      event.currentTarget.closest(".ws-chat__menuwrap")
                        ?.querySelector<HTMLElement>(".ws-chat__more")?.focus();
                      setMenuFor(null);
                      setDeleteError(null);
                      setDeleting(conversation);
                    }}>
              <IconTrash size={14} /> Delete
            </button>
          </span>
        ) : null}
      </span>
    );
  }

  return (
    <div className="ws-chat" data-rail={railHidden ? "hidden" : undefined}>
      {/* ---- the sidebar (assistant-ui's thread-list sidebar) -------------- */}
      {/* A native disclosure: always open on a wide screen, and a real drawer on a
          phone with no state to keep in sync. */}
      <details className="ws-chat__rail" ref={railRef} open>
        <summary className="ws-chat__railtoggle">
          <IconMessage size={15} /> Chats
        </summary>
        <div className="ws-chat__railbody">
          <div className="ws-chat__brand">
            <Link className="ws-chat__brandlink" href="/dashboard">
              <span className="ws-chat__brandmark" aria-hidden="true"><IconMessage size={15} /></span>
              <span><span className="ws-shell__word-a">Legal</span><span className="ws-shell__word-b">Mind</span></span>
            </Link>
            <button type="button" className="ws-chat__iconbtn ws-chat__collapse"
                    aria-label="Hide sidebar" title="Hide sidebar"
                    onClick={() => { railToggledRef.current = true; setRailHidden(true); }}>
              <IconPanel size={16} />
            </button>
          </div>
          <Link className="ws-chat__new" href="/dashboard/ask" onClick={resetChat}>
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
                      <li key={conversation.id} className="ws-chat__railrow"
                          data-open={menuFor?.id === conversation.id && menuFor.at === "rail"
                            ? "" : undefined}>
                        <Link
                          className="ws-chat__railitem"
                          href={`/dashboard/ask?id=${conversation.id}`}
                          aria-current={conversation.id === activeId ? "page" : undefined}
                          /* the whole name and what it is about, for a title the row cuts short */
                          title={`${chatTitle(conversation)} — ${
                            conversation.document_name ?? "Company knowledge"}`}
                        >
                          {chatTitle(conversation)}
                        </Link>
                        {chatMenu(conversation, "rail")}
                      </li>
                    ))}
                  </ul>
                </div>
              ))
            )}
          </nav>
        </div>
        {/* Where the demo has "Sign in": who is signed in, and the way out. The rest of
            LegalMind is the logo's link — this full-screen page has no top bar. */}
        <div className="ws-chat__railfoot ws-chat__menuwrap">
          <button type="button" className="ws-chat__account"
                  aria-expanded={accountOpen}
                  aria-label={`Account menu for ${identity?.name ?? ""}`}
                  onClick={() => setMenuFor(accountOpen ? null : { id: "account", at: "account" })}>
            {/* The same circle as the top bar: the Google profile photo for a Google
                sign-in, the account's first letter otherwise. */}
            <Avatar name={identity?.name || identity?.email || "?"} picture={identity?.picture} />
            <span className="ws-chat__footwho">{identity?.name}</span>
            <IconChevronUp size={14} />
          </button>
          {accountOpen ? (
            <div className="ws-menu__list ws-chat__menu ws-chat__accountmenu"
                 role="group" aria-label="Account">
              <div className="ws-shell__who">
                <strong>{identity?.name}</strong>
                <span>{identity?.email}</span>
                {identity?.department ? <span>{identity.department.name}</span> : null}
              </div>
              <button type="button" className="ws-menu__item"
                      onClick={() => { setMenuFor(null); void signOut(); }}>
                <IconSignOut size={14} /> Sign out
              </button>
            </div>
          ) : null}
        </div>
      </details>

      {/* ---- the conversation -------------------------------------------- */}
      <AssistantRuntimeProvider runtime={runtime}>
      <section className="ws-chat__main" aria-label="Conversation">
        <header className="ws-chat__head">
          {railHidden ? (
            <button type="button" className="ws-chat__iconbtn ws-chat__collapse"
                    aria-label="Show sidebar" title="Show sidebar"
                    onClick={() => { railToggledRef.current = true; setRailHidden(false); }}>
              <IconPanel size={16} />
            </button>
          ) : null}
          <h1 className="ws-chat__title">
            {(activeChat && chatTitle(activeChat)) || "New chat"}
          </h1>
          {scope.contractId ? (
            <p className="ws-chat__scope">
              <IconFile size={13} /> About{" "}
              <Link href={`/dashboard?id=${scope.contractId}`}>
                {scope.documentName ?? "this document"}
              </Link>
            </p>
          ) : null}
          <span className="ws-chat__headspacer" />
          {activeChat ? chatMenu(activeChat, "head") : null}
        </header>

        <Thread
          empty={!loadingChat && !notFound && turns.length === 0 && shownPending === null}
          welcome={{ title: "How can I help you today?" }}
          suggestions={[...OPENERS, scope.contractId ? DOCUMENT_OPENER : KNOWLEDGE_OPENER]}
          onSuggestion={(opener) => {
            runtime.thread.composer.setText(opener);
            inputRef.current?.focus();
          }}
          renderAnswer={(turn) => (
            <TranscriptTurn
              turn={turn}
              contractId={scope.contractId}
              comparisonReviewId={turn.routed_to_evaluator ? reviewId : null}
            />
          )}
          progress={
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
          }
          viewportRef={logRef}
          onJump={focusLog}
          composer={{
            inputRef,
            onKeyDown: enterSends(runtime),
            describedBy: "ws-chat-count",
            top: (
              <>
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
                      Read in this chat only. Not added to the Dashboard.
                    </span>
                  </div>
                ) : null}
              </>
            ),
            start: canUpload ? (
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
                  className="ws-chat__iconbtn ws-chat__attach"
                  aria-label="Add files"
                  title="Add files"
                  onClick={() => fileRef.current?.click()}
                  disabled={busy}
                >
                  <IconPlus size={16} />
                </button>
              </>
            ) : null,
            end: <ModelPicker models={models} value={shownModel} disabled={busy}
                              onChange={chooseModel} />,
            below: (
              <>
                <QuestionCount />
                <p className="ws-chat__note">
                  Answers cite the material they came from, or say they cannot. Verify
                  against the original document.
                </p>
              </>
            ),
          }}
        >
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
          {error ? (
            <div className="ws-state ws-state--error" role="alert">
              <p>{typeof error === "string" ? error : describeError(error)}</p>
              {failed ? (
                <button type="button" className="ws-btn ws-btn--sm"
                        // The edit again only while its question still exists.
                        onClick={() => void submit(failed.text,
                          turns.some((turn) => turn.id === failed.editOf)
                            ? failed.editOf : undefined)}>
                  Try again
                </button>
              ) : null}
            </div>
          ) : null}
          <p className="ws-visually-hidden" role="status" aria-atomic="true">{announce}</p>
        </Thread>
      </section>
      </AssistantRuntimeProvider>

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
