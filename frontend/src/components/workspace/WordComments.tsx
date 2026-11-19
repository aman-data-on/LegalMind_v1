/**
 * The Word comments made on a passage — the client's, or ours to a reader of positions —
 * one quiet line each: "Comment from {author}", then their words. Shared by the document
 * (each row), the Changes tab's passage and its answer card, so a comment reads the same
 * everywhere. Presentation only: the server decides which comments a reader gets.
 */
import type { WordComment } from "@/lib/types";
import { CHANGES_COPY } from "@/lib/labels";

export function CommentLines({ comments }: { comments: WordComment[] }) {
  return (
    <>
      {comments.map((n, i) => (
        <p key={i}>
          <span className="ws-row__noteskind">{CHANGES_COPY.commentFrom(n.author)}</span> {n.text}
        </p>
      ))}
    </>
  );
}

/** A change's comments as their own block (the passage and the answer card). */
export function WordComments({ comments }: { comments?: WordComment[] | undefined }) {
  if (!comments?.length) return null;
  return (
    <div className="ws-row__notes" role="note" aria-label={CHANGES_COPY.commentsLabel}>
      <CommentLines comments={comments} />
    </div>
  );
}
