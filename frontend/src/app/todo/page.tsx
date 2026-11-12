"use client";

/**
 * To-do — what is waiting on me (`AM-264`, CLM R8). Every item is resolved by the server
 * (`GET /todo`): a fixed sentence, the contract, how long it has waited and where to act.
 * The SAME list as the home's queue (`AM-291`: one task per contract per person), oldest
 * first. This page decides nothing and filters nothing (rule 18).
 */

import { PageHeader } from "@/components/page/PageHeader";
import { TaskList, TodoViews, useTasks } from "@/components/workspace/TodoViews";
import { ErrorState, LoadingState } from "@/components/Feedback";

export default function TodoPage() {
  const { tasks, contracts, error, reload } = useTasks();
  return (
    <div className="lm-page ws-home">
      <PageHeader title="To-do"
                  meta={tasks?.length ? <span>{tasks.length === 1 ? "1 task waiting on you" : `${tasks.length} tasks waiting on you`}</span> : null} />
      <TodoViews />
      {error ? <ErrorState title="Your to-do could not be loaded" error={error} onRetry={reload} /> : null}
      {tasks === null && !error ? <LoadingState label="Loading your to-do…" rows={4} /> : null}
      {tasks !== null && tasks.length === 0 ? (
        <p className="ws-hq__clear">
          Nothing is waiting on you. Decisions, client replies and answers to your questions appear here.
        </p>
      ) : null}
      {tasks?.length ? <section className="ws-hq" aria-label="Waiting on you"><TaskList tasks={tasks} contracts={contracts} /></section> : null}
    </div>
  );
}
