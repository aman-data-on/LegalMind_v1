import { ReviewReportPage } from "@/components/workspace/ReviewReportPage";

/** Server page, thin: resolves the route param and hands it to the client leaf. */
export default async function ReviewReportRoute({
  params,
}: {
  params: Promise<{ reviewId: string }>;
}) {
  const { reviewId } = await params;
  return <ReviewReportPage reviewId={reviewId} />;
}
