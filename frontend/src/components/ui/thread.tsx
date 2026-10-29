"use client";

/**
 * The Ask thread — assistant-ui's generated `Thread` starter (r.assistant-ui.com
 * `thread`, for @assistant-ui/react 0.15), cut down to what this backend produces
 * and drawn in LegalMind's tokens (the `@theme` mapping in globals.css).
 *
 * Kept from the starter: the centred welcome with the composer under it, the
 * top-anchored viewport, the user bubble, the assistant message with its action
 * bar, the round scroll-to-bottom control and the composer shell.
 *
 * Left out, because nothing here can produce them: voice, dictation, tool calls,
 * reasoning, branches, earlier-page loading, follow-up suggestions, image/file parts
 * and "Refresh". Editing a question is kept (`AM-134`): the server replaces it and
 * every turn after it, so what is shown is what is stored. Refresh is not — it would
 * show one answer and store two; a failed question is resent with "Try again".
 *
 * The answer's body is the caller's (`renderAnswer`): citations, Sources and
 * routed Findings keep the renderer that enforces their rules. It lives in
 * `components/ui` because that is the one directory globals.css compiles
 * utilities from (DD-22).
 */

import {
  ActionBarPrimitive,
  AuiIf,
  ComposerPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  useAuiState,
  useThreadViewport,
} from "@assistant-ui/react";
import {
  ArrowDownIcon, ArrowUpIcon, CheckIcon, ChevronDownIcon, CopyIcon, PencilIcon, SquareIcon,
} from "lucide-react";
import {
  forwardRef,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type ClipboardEvent,
  type ComponentPropsWithoutRef,
  type KeyboardEvent,
  type ReactNode,
  type Ref,
} from "react";

import type { ConversationTurn } from "@/lib/types";
import { cn } from "@/lib/utils";

/** The starter's `TooltipIconButton`, on the native `title` instead of a Radix
 *  tooltip: the same label for sighted and screen-reader users, no new package. */
const IconButton = forwardRef<HTMLButtonElement, ComponentPropsWithoutRef<"button"> & {
  label: string;
}>(({ label, className, children, ...rest }, ref) => (
  <button
    ref={ref}
    type="button"
    title={label}
    aria-label={label}
    className={cn(
      "text-muted-foreground hover:bg-accent hover:text-foreground inline-flex size-7 items-center justify-center rounded-md border-0 bg-transparent p-0 [&_svg]:size-4",
      className,
    )}
    {...rest}
  >
    {children}
  </button>
));
IconButton.displayName = "IconButton";

export interface ThreadProps {
  /** No turn yet: the welcome shows and the composer sits in the middle. */
  empty: boolean;
  /** `as: "p"` where a heading above already names the surface. */
  welcome: { title: string; as?: "h2" | "p" };
  /** Openers as editable drafts — choosing one fills the box and sends nothing. */
  suggestions: readonly string[];
  onSuggestion: (text: string) => void;
  renderAnswer: (turn: ConversationTurn) => ReactNode;
  /** Beside Copy under an answer: the reader's rating (`AM-226` r9). */
  renderAnswerActions?: (turn: ConversationTurn) => ReactNode;
  /** Above a question: the files it was sent with (`AM-226` r7). */
  renderQuestionFiles?: (turn: ConversationTurn) => ReactNode;
  /** The answer being found, until it arrives. */
  progress: ReactNode;
  /** After the messages: loading, not found, the error with Try again, the live region. */
  children?: ReactNode;
  viewportRef: Ref<HTMLDivElement>;
  /** Fired by the scroll control: focus goes to the log it scrolled, not the page. */
  onJump: () => void;
  composer: {
    inputRef: Ref<HTMLTextAreaElement>;
    onKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void;
    /** Outside the box, above it: the chat's saved files (`AM-226`). */
    above?: ReactNode;
    /** Inside the box, above the text: the files about to be attached. */
    top?: ReactNode;
    start?: ReactNode;
    end?: ReactNode;
    /** Under the box and the openers: the character count and the standing note. */
    /** A state of the input itself (`AM-222`: AI answers paused), shown inside its frame. */
    notice?: ReactNode;
    below?: ReactNode;
    /** The box's own id, accessible name and placeholder — each surface names its own. */
    inputId?: string;
    label?: string;
    placeholder?: string;
    /** The id of the text that describes the box (the Ask page's character count). */
    describedBy?: string;
    /** A long paste can become an attachment instead of text in the box (the Ask page). */
    onPaste?: (event: ClipboardEvent<HTMLTextAreaElement>) => void;
    /** Why Send waits, said beside it (`AM-226`): the chosen model cannot answer. */
    sendBlocked?: string | null;
    /** Sends an empty box: attached files alone are a question (`AM-226`). */
    sendEmpty?: (() => void) | null;
  };
}

export function Thread({
  empty, welcome, suggestions, onSuggestion, renderAnswer, renderQuestionFiles, renderAnswerActions, progress, children,
  viewportRef, onJump, composer,
}: ThreadProps) {
  const Welcome = welcome.as ?? "h2";
  return (
    <ThreadPrimitive.Root
      className="@container flex min-h-0 flex-1 flex-col bg-background"
      style={{
        ["--thread-max-width" as string]: "var(--ws-chat-measure, 48rem)",
        ["--composer-radius" as string]: "1rem",
      }}
    >
      {/* A tab stop: a conversation of refusals holds no link or button, and a region
          that scrolls must be reachable by keyboard to be scrolled by one (WCAG 2.1.1).
          The viewport never clamps a turn; a long question folds in its own bubble. */}
      <ThreadPrimitive.Viewport
        ref={viewportRef}
        tabIndex={0}
        role="region"
        aria-label="Messages"
        data-slot="aui_thread-viewport"
        turnAnchor="top"
        topAnchorMessageClamp={{ tallerThan: "100000px", visibleHeight: "100000px" }}
        className="relative flex flex-1 flex-col overflow-y-auto focus-visible:outline-none"
      >
        <div className={cn(
          "mx-auto flex w-full max-w-(--thread-max-width) flex-1 flex-col px-4 pt-6",
          empty && "max-w-2xl",
          empty && "justify-center",
        )}>
          {empty ? (
            <Welcome data-slot="aui_thread-welcome"
                className="text-foreground text-center font-semibold tracking-tight">
              {welcome.title}
            </Welcome>
          ) : null}

          <div data-slot="aui_message-group" className="mb-10 flex flex-col gap-y-6 empty:hidden">
            <ThreadPrimitive.Messages>
              {({ message }) => {
                const turn = message.metadata.custom.turn as ConversationTurn | undefined;
                // Only a question the server has named can be edited — not the one being
                // answered, nor one whose id the server did not return.
                if (message.role === "user") {
                  return <UserMessage text={turn?.content ?? ""}
                                      files={turn && renderQuestionFiles ? renderQuestionFiles(turn) : null}
                                      editable={!!turn && UUID.test(turn.id)
                                                && turn.content !== MATERIAL_TURN} />;
                }
                return (
                  <AssistantMessage actions={turn && renderAnswerActions ? renderAnswerActions(turn) : null}>
                    {turn ? renderAnswer(turn) : progress}
                  </AssistantMessage>
                );
              }}
            </ThreadPrimitive.Messages>
            {children}
          </div>

          <ThreadPrimitive.ViewportFooter className={cn(
            "flex flex-col gap-3 bg-background pb-4 md:pb-6",
            !empty && "sticky bottom-0 mt-auto",
          )}>
            <ScrollToBottom onJump={onJump} />
            <Composer {...composer} />
            {empty && suggestions.length > 0 ? (
              // The starter's rule: the openers step aside once the reader starts typing.
              <AuiIf condition={(s) => s.composer.isEmpty}>
              <div role="group" aria-label="Example questions"
                   className="flex w-full flex-wrap justify-center gap-2">
                {suggestions.map((text) => (
                  <button
                    key={text}
                    type="button"
                    onClick={() => onSuggestion(text)}
                    className="border-border bg-background text-muted-foreground hover:bg-accent hover:text-foreground rounded-md border px-3 py-1.5 text-sm"
                  >
                    {text}
                  </button>
                ))}
              </div>
              </AuiIf>
            ) : null}
            {composer.below}
          </ThreadPrimitive.ViewportFooter>
        </div>
      </ThreadPrimitive.Viewport>
    </ThreadPrimitive.Root>
  );
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
/** The server's stand-in for a bare paste (`attachments.MATERIAL_TURN`, kept equal by a
 *  backend test): not a question the reader wrote, so there is nothing to edit. */
export const MATERIAL_TURN = "[Pasted text saved as an attachment]";

/** The reader's message, as other chat apps show it (owner, 2026-10-13): a long one folds
 *  inside its bubble with "Show more"; copy and edit sit under it. The whole text stays in
 *  the page when folded, so a screen reader and a copy still get every word. */
function UserMessage({ text, editable, files }: {
  text: string; editable: boolean; files?: ReactNode;
}) {
  const editing = useAuiState((s) => s.message.composer.isEditing);
  // While any chat is being answered nothing can be sent, so an edit would close and be
  // lost without a word — Edit waits too (review, 2026-10-14).
  const sendDisabled = useAuiState((s) => s.thread.isSendDisabled);
  const [open, setOpen] = useState(false);
  // "Show more" only when the text is really cut: measured on the folded box, so a short
  // question never carries the control and one long line is caught too.
  const body = useRef<HTMLDivElement>(null);
  const [clipped, setClipped] = useState(false);
  useLayoutEffect(() => {
    const node = body.current;
    if (node && !open) setClipped(node.scrollHeight > node.clientHeight + 1);
  }, [text, open]);
  return (
    <MessagePrimitive.Root
      data-role="user"
      className="ws-turn--user group grid grid-cols-[minmax(72px,1fr)_auto] px-2"
    >
      {editing ? <EditComposer /> : (
        <div className="col-start-2 min-w-0">
          {files}
          <div className="bg-muted text-foreground rounded-(--composer-radius) px-4 py-2">
            <div ref={body} className={cn("whitespace-pre-wrap wrap-break-word",
                                         !open && "line-clamp-10")}>
              <span className="sr-only">You: </span>
              {text}
            </div>
            {clipped ? (
              <button type="button" aria-expanded={open} onClick={() => setOpen(!open)}
                      className="text-muted-foreground hover:text-foreground mt-2 inline-flex items-center gap-1 border-0 bg-transparent p-0 text-sm">
                {open ? "Show less" : "Show more"}
                <ChevronDownIcon aria-hidden="true"
                                 className={cn("size-4 transition-transform", open && "rotate-180")} />
              </button>
            ) : null}
          </div>
          {/* Copy and edit under the question: shown when it is pointed at or tabbed
              into, and always on a touch screen, which has no pointer to point with. */}
          <ActionBarPrimitive.Root hideWhenRunning autohide="never"
            className="mt-1 flex justify-end gap-2 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100 [@media(hover:none)]:opacity-100">
            <ActionBarPrimitive.Copy asChild>
              <IconButton label="Copy question">
                <AuiIf condition={(s) => s.message.isCopied}><CheckIcon /></AuiIf>
                <AuiIf condition={(s) => !s.message.isCopied}><CopyIcon /></AuiIf>
              </IconButton>
            </ActionBarPrimitive.Copy>
            {editable && !sendDisabled ? (
              <ActionBarPrimitive.Edit asChild>
                <IconButton label="Edit question"><PencilIcon /></IconButton>
              </ActionBarPrimitive.Edit>
            ) : null}
          </ActionBarPrimitive.Root>
        </div>
      )}
    </MessagePrimitive.Root>
  );
}

/** The starter's edit composer: the question in place, sent as an edit — it and every
 *  later turn are replaced (`AM-134`). */
function EditComposer() {
  return (
    <ComposerPrimitive.Root
      data-slot="aui_edit-composer"
      className="border-border bg-background col-span-full ms-auto flex w-full max-w-[85%] flex-col rounded-xl border"
    >
      <ComposerPrimitive.Input
        autoFocus
        aria-label="Edit your question"
        className="text-foreground min-h-14 w-full resize-none rounded-none border-0 bg-transparent px-4 pt-3 pb-1 text-base outline-none"
      />
      <div className="mx-2.5 mb-2.5 flex items-center gap-1.5 self-end">
        <ComposerPrimitive.Cancel className="text-foreground hover:bg-accent h-8 rounded-md border-0 bg-transparent px-3 text-sm">
          Cancel
        </ComposerPrimitive.Cancel>
        <ComposerPrimitive.Send className="bg-primary text-primary-foreground disabled:bg-muted-foreground/50 h-8 rounded-md border-0 px-3 text-sm">
          Send
        </ComposerPrimitive.Send>
      </div>
    </ComposerPrimitive.Root>
  );
}

function AssistantMessage({ children, actions }: { children: ReactNode; actions?: ReactNode }) {
  return (
    <MessagePrimitive.Root data-role="assistant" className="relative">
      <div className="text-foreground px-2 leading-relaxed wrap-break-word">{children}</div>
      <div className="ms-2 flex min-h-7.5 flex-wrap items-center gap-x-1 pt-1.5">
        <ActionBarPrimitive.Root hideWhenRunning autohide="not-last"
                                 className="text-muted-foreground -ms-1 flex gap-1">
          <ActionBarPrimitive.Copy asChild>
            <IconButton label="Copy answer">
              <AuiIf condition={(s) => s.message.isCopied}><CheckIcon /></AuiIf>
              <AuiIf condition={(s) => !s.message.isCopied}><CopyIcon /></AuiIf>
            </IconButton>
          </ActionBarPrimitive.Copy>
        </ActionBarPrimitive.Root>
        {actions}
      </div>
    </MessagePrimitive.Root>
  );
}

/** Shown only away from the end. An answer that finished while the reader was further
 *  up is said on the control instead of moving them (2026-10-06). */
function ScrollToBottom({ onJump }: { onJump: () => void }) {
  const atBottom = useThreadViewport((s) => s.isAtBottom);
  const running = useAuiState((s) => s.thread.isRunning);
  const [unseen, setUnseen] = useState(false);
  const wasRunning = useRef(running);
  useEffect(() => {
    if (atBottom) setUnseen(false);
    else if (wasRunning.current && !running) setUnseen(true);
    wasRunning.current = running;
  }, [atBottom, running]);
  if (atBottom) return null;
  const label = unseen ? "New answer below" : "Jump to latest";
  return (
    <ThreadPrimitive.ScrollToBottom asChild>
      <button
        type="button"
        title={label}
        aria-label={label}
        onClick={onJump}
        className="border-border bg-background text-foreground hover:bg-accent absolute -top-12 z-10 inline-flex items-center gap-1.5 self-center rounded-full border px-3 py-2 text-sm shadow-sm [&_svg]:size-4"
      >
        <ArrowDownIcon aria-hidden />
        {unseen ? <span>{label}</span> : null}
      </button>
    </ThreadPrimitive.ScrollToBottom>
  );
}

function Composer({
  inputRef, onKeyDown, notice, above, top, start, end, inputId = "ws-chat-question", label = "Your question",
  placeholder = "Send a message…", describedBy, onPaste, sendBlocked, sendEmpty,
}: ThreadProps["composer"]) {
  const sendClass = "bg-primary text-primary-foreground disabled:bg-muted-foreground/50 disabled:text-primary-foreground inline-flex size-7 items-center justify-center rounded-md border-0 p-0 [&_svg]:size-4";
  return (
    <ComposerPrimitive.Root className="relative flex w-full flex-col gap-1.5">
      {above}
      <div
        data-slot="aui_composer-shell"
        className="border-border focus-within:border-muted-foreground bg-background flex w-full cursor-text flex-col gap-1 rounded-xl border p-2"
      >
        {notice}
        {top}
        <label className="sr-only" htmlFor={inputId}>{label}</label>
        {/* Editable while an answer is found; sending waits (`isSendDisabled`). No
            `maxLength`: it cut a pasted email at 2,000 characters without a word. */}
        <ComposerPrimitive.Input
          id={inputId}
          ref={inputRef}
          rows={1}
          placeholder={placeholder}
          aria-describedby={describedBy}
          onPaste={onPaste}
          // Enter is the caller's: the library's misses Safari's IME Enter (keyCode 229).
          submitMode="none"
          // Escape in the box is the reader's (closing an IME, clearing a thought), never
          // a Stop: the square button is the one way to abandon an answer.
          cancelOnEscape={false}
          onKeyDown={onKeyDown}
          className="placeholder:text-muted-foreground max-h-48 min-h-9 w-full resize-none rounded-none border-0 bg-transparent px-2 py-1 text-base leading-6 outline-none"
        />
        <div className="flex items-center justify-between gap-2">
          <div className="flex min-w-0 items-center gap-1">{start}{end}</div>
          <div className="flex items-center gap-1.5">
            {sendBlocked ? (
              // Only in Send's place: while an answer runs, Stop stands alone.
              <AuiIf condition={(s) => !s.thread.isRunning}>
                <span id={`${inputId}-blocked`} className="ws-chat__blocked">{sendBlocked}</span>
                <button type="button" disabled aria-label="Send question"
                        aria-describedby={`${inputId}-blocked`} className={sendClass}>
                  <ArrowUpIcon aria-hidden />
                </button>
              </AuiIf>
            ) : (
              <>
                <AuiIf condition={(s) => !s.thread.isRunning && !(sendEmpty && s.composer.isEmpty)}>
                  <ComposerPrimitive.Send aria-label="Send question" title="Send question"
                                          className={sendClass}>
                    <ArrowUpIcon aria-hidden />
                  </ComposerPrimitive.Send>
                </AuiIf>
                {sendEmpty ? (
                  <AuiIf condition={(s) => !s.thread.isRunning && s.composer.isEmpty}>
                    <button type="button" aria-label="Send question" title="Send question"
                            className={sendClass} onClick={sendEmpty}>
                      <ArrowUpIcon aria-hidden />
                    </button>
                  </AuiIf>
                ) : null}
              </>
            )}
            <AuiIf condition={(s) => s.thread.isRunning}>
              <ComposerPrimitive.Cancel
                aria-label="Stop answering"
                title="Stop answering"
                className="bg-primary text-primary-foreground inline-flex size-7 items-center justify-center rounded-md border-0 p-0"
              >
                <SquareIcon aria-hidden className="size-3.5 fill-current" />
              </ComposerPrimitive.Cancel>
            </AuiIf>
          </div>
        </div>
      </div>
    </ComposerPrimitive.Root>
  );
}
