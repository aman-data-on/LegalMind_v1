import { WorkspacePage } from "@/components/workspace/WorkspacePage";

/** Server page, thin: resolves the route param and hands it to the client leaf. */
export default async function WorkspaceRoute({
  params,
}: {
  params: Promise<{ contractId: string }>;
}) {
  const { contractId } = await params;
  return <WorkspacePage contractId={contractId} />;
}
