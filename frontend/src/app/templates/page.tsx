"use client";

import { TemplateLibrary } from "@/components/templates/TemplateList";
import { TemplatePlaybooks } from "@/components/templates/TemplatePlaybooks";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";

import { NotHere } from "./NotHere";

/** Templates (`AM-316`): one page for everyone who makes contracts and for Legal, with
 *  what we can offer beneath it for a reader of our positions (`AM-305`). Presentation
 *  only — the server gates every part (rule 18). */
export default function TemplatesPage() {
  const { can } = useSession();
  if (!can(P.CONTRACT_CREATE) && !can(P.LEGAL_APPROVE_CUSTOMIZATION)) return <NotHere />;
  return (
    <>
      <TemplateLibrary />
      {can(P.LEGAL_POSITION_VIEW) ? <div className="lm-page tpl tpl--list"><TemplatePlaybooks /></div> : null}
    </>
  );
}
