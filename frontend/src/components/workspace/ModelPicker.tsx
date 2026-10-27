"use client";

/**
 * The model the question goes to (`AM-116`) — a compact picker in the composer.
 *
 * Radix Select rather than a native `<select>`: a native control is as wide as its
 * longest option ("DeepSeek (not configured)"), so "Gemini" sat in a stretched pill
 * with its chevron far away. The trigger here is as wide as the chosen name, and the
 * menu says plainly which models the server can serve. A model that is not configured
 * stays choosable — the server refuses it by name, and so does the composer, before a
 * chat is created — so the reader is never shown one as working when it is not.
 *
 * Portalled into `.ws`, not `document.body`, for the reason `Dialog.tsx` records: every
 * token this CSS uses is scoped to `.ws`.
 */

import * as Select from "@radix-ui/react-select";
import { type RefObject, useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import type { AskModel } from "@/lib/types";

import { IconCheck, IconChevronDown, IconPause } from "./icons";

export function ModelPicker({
  models,
  value,
  disabled,
  onChange,
}: {
  models: AskModel[];
  value: string;
  disabled: boolean;
  onChange: (id: string) => void;
}) {
  const chosen = models.find((m) => m.id === value) ?? models.find((m) => m.default) ?? models[0];
  if (!chosen) return null;
  return (
    <Select.Root value={chosen.id} onValueChange={onChange} disabled={disabled}>
      <Select.Trigger
        className="ws-chat__model"
        aria-label={`Model: ${chosen.label}${chosen.configured ? "" : ", not configured"}`}
        data-unconfigured={chosen.configured ? undefined : ""}
      >
        <Select.Value>{chosen.label}</Select.Value>
        <Select.Icon className="ws-chat__modelchev">
          <IconChevronDown size={14} />
        </Select.Icon>
      </Select.Trigger>
      <Select.Portal container={typeof document === "undefined" ? null : document.querySelector<HTMLElement>(".ws")}>
        <Select.Content className="ws-chat__modelmenu" position="popper" side="top" align="end"
                        sideOffset={8} collisionPadding={12}>
          <Select.Viewport>
            <Select.Group>
              <Select.Label className="ws-chat__modelhead">Answer with</Select.Label>
              {models.map((m) => (
                <Select.Item key={m.id} value={m.id} className="ws-chat__modelitem">
                  <span className="ws-chat__modelname">
                    {/* the option's accessible name is its ItemText alone, so the
                        status is in it too — "DeepSeek" was all a screen reader said */}
                    <Select.ItemText>
                      {m.label}
                      {m.configured ? null : <span className="visually-hidden">(not configured)</span>}
                    </Select.ItemText>
                    <span className="ws-chat__modelnote">
                      {m.configured ? (m.default ? "Default" : "Available") : "Not configured"}
                    </span>
                  </span>
                  <Select.ItemIndicator className="ws-chat__modelcheck">
                    <IconCheck size={15} />
                  </Select.ItemIndicator>
                </Select.Item>
              ))}
            </Select.Group>
          </Select.Viewport>
        </Select.Content>
      </Select.Portal>
    </Select.Root>
  );
}

/** Shown in the picker until `GET /ask/models` names the server's own default. */
export const FALLBACK_MODEL = "gemini";

/** What the server says when a model is listed but cannot be served — said here too,
 *  so a chat is not created for a question nobody can answer. */
export function notConfigured(model: AskModel): string {
  return `${model.label} is not configured yet. Choose Gemini to ask this question.`;
}

/** The composer's model list and choice (`AM-116`), shared by the Ask page and the
 *  document's Ask panel — the panel had no picker at all (2026-10-15). An empty list
 *  (it failed to load) hides the control and the question goes to the server's
 *  default. The choice is the CHAT's (`AM-122`): read from the chat when one is opened
 *  (`setModel(detail.model)`), stored on the server when the reader changes it, and a
 *  new chat starts on the default. `model === null` is "never chosen": no model is
 *  sent and the server's default answers. */
export function useChatModel(enabled: boolean, chatRef: RefObject<string | null>,
                             onError: (cause: unknown) => void) {
  const [models, setModels] = useState<AskModel[]>([]);
  const [model, setModel] = useState<string | null>(null);
  const saving = useRef<Promise<void>>(Promise.resolve());
  useEffect(() => {
    if (enabled) api.askModels().then(setModels, () => setModels([]));
  }, [enabled]);
  useEffect(() => {   // AM-222: look again each minute, so a pause shows and leaves by itself
    if (!enabled) return;
    const timer = setInterval(() => api.askModels().then(setModels, () => undefined), 60_000);
    return () => clearInterval(timer);
  }, [enabled]);
  const shown = model ?? models.find((m) => m.default)?.id ?? FALLBACK_MODEL;

  /** The reader's choice becomes the open chat's at once, so the next turn — from this
   *  tab or any other — goes to it. A chat not yet created takes the choice with its
   *  first question. */
  function choose(id: string) {
    setModel(id);
    onError(null);
    const chat = chatRef.current;
    if (!chat) return;
    // One save after another, in the order chosen: two quick switches sent together can
    // reach the server the other way round and leave the chat on the earlier choice.
    saving.current = saving.current
      .then(() => api.updateConversation(chat, { model: id }))
      .then(() => undefined, (cause) => {
        if (chatRef.current === chat) onError(cause);
      });
  }

  /** The chosen model when the server cannot serve it: the question is not sent. */
  const unconfigured = models.find((m) => m.id === shown && !m.configured) ?? null;
  const paused = models.find((m) => m.id === shown && m.paused) ?? null;
  return { models, model, setModel, shown, choose, unconfigured, paused };
}

const PAUSE_CAUSE = { payment: "credit ran out", quota: "usage limit was reached" } as const;

/** AI answers paused (`AM-222`), said on the question box itself before the reader
 *  types: what stopped, what still works. The cause and its time go to a platform
 *  administrator only — the server sends them to no one else. */
export function PausedNotice({ model }: { model: AskModel | null }) {
  if (!model) return null;
  const why = model.paused_reason;
  return (
    <div className="ws-paused" role="status">
      <span className="ws-paused__icon"><IconPause size={16} /></span>
      <div>
        <p className="ws-paused__title">AI answers are paused</p>
        <p className="ws-paused__line">Your chats, contracts and reviews are all still here. Try again later.</p>
        {why ? (
          <p className="ws-paused__admin">
            For admins: {model.label}&rsquo;s {PAUSE_CAUSE[why.kind]} on{" "}
            {new Date(why.since).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}.
            Answers resume on their own once it is restored.
          </p>
        ) : null}
      </div>
    </div>
  );
}
