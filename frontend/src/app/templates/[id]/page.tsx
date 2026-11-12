"use client";

import { useParams } from "next/navigation";

import { TemplateApproval } from "@/components/templates/TemplateApproval";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";

import { NotHere } from "../NotHere";

export default function TemplatePage() {
  const { can } = useSession();
  const { id } = useParams<{ id: string }>();
  return can(P.LEGAL_APPROVE_CUSTOMIZATION) ? <TemplateApproval id={id} /> : <NotHere />;
}
