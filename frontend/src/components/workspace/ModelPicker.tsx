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

import type { AskModel } from "@/lib/types";

import { IconCheck, IconChevronDown } from "./icons";

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
