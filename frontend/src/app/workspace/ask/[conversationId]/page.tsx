import { ConversationView } from "@/components/workspace/ConversationView";

/** Server page, thin: resolves the route param and hands it to the client leaf. */
export default async function ConversationRoute({
  params,
}: {
  params: Promise<{ conversationId: string }>;
}) {
  const { conversationId } = await params;
  return <ConversationView conversationId={conversationId} />;
}
