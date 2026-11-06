"use client";

import { TemplateList } from "@/components/templates/TemplateList";
import { TemplatePlaybooks } from "@/components/templates/TemplatePlaybooks";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";

import { NotHere } from "./NotHere";

/** The lawyer's template list, with what sales can offer beneath it; for the sales team
 *  (`AM-305`), only what we can offer on each published template. Presentation only —
 *  the server gates both (rule 18). */
export default function TemplatesPage() {
  const { can } = useSession();
  const sales = can(P.CONTRACT_CREATE) && can(P.LEGAL_POSITION_VIEW);
  if (can(P.LEGAL_APPROVE_CUSTOMIZATION)) {
    return <><TemplateList />{sales ? <div className="lm-page tpl tpl--list"><TemplatePlaybooks /></div> : null}</>;
  }
  return sales ? <TemplatePlaybooks header /> : <NotHere />;
}
