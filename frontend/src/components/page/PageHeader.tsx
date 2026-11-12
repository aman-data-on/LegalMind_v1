/**
 * The ONE page header (cross-page pass, IBM Carbon / Atlassian page-header anatomy):
 *
 *   ← Back to <where>                                  (a text link, never an icon alone)
 *   Title                              secondary · secondary · ⋯ · [Primary]
 *   stage · owner · …                  (meta: facts, each a word that means something)
 *   children                            (the page's own bar: tabs, version)
 *
 * At most ONE filled button — the `primary` slot, which the page fills from `nextStep`.
 * Presentation only; every action it holds checks again server-side (rule 18).
 */

import Link from "next/link";
import type { ReactNode } from "react";

import { IconArrowLeft } from "@/components/workspace/icons";

export function PageHeader({ title, back, meta, secondary, primary, children, wide = false }: {
  title: ReactNode;
  back?: { href: string; label: string };
  meta?: ReactNode;
  secondary?: ReactNode;
  primary?: ReactNode;
  children?: ReactNode;
  /** a workspace (contract, template): the header spans the screen; else the page width */
  wide?: boolean;
}) {
  return (
    <header className={`lm-ph${wide ? " lm-ph--wide" : ""}`}>
      {back ? (
        <Link className="lm-ph__back" href={back.href}>
          <IconArrowLeft size={14} /> {back.label}
        </Link>
      ) : null}
      <div className="lm-ph__row">
        <div className="lm-ph__id">
          <h1 className="lm-ph__title">{title}</h1>
          {meta ? <div className="lm-ph__meta">{meta}</div> : null}
        </div>
        {secondary || primary ? (
          <div className="lm-ph__acts">{secondary}{primary}</div>
        ) : null}
      </div>
      {children}
    </header>
  );
}
