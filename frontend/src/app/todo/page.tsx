"use client";

/**
 * To-do — what is waiting on me (`AM-264`, CLM R8). Every item is resolved by the server
 * (`GET /todo`): a fixed sentence, the contract, how long it has waited and where to act.
 * The SAME list as the home's queue (`AM-291`: one task per contract per person), oldest
 * first. This page decides nothing and filters nothing (rule 18).
 */

import { PageHeader } from "@/components/page/PageHeader";
import { TaskList, TodoViews, useTasks } from "@/components/workspace/TodoViews";
import { describeError } from "@/lib/api";

export default function TodoPage() {
  const { tasks, contracts, error } = useTasks();
  return (
    <div className="lm-page ws-home">
      <PageHeader title="To-do"
                  meta={tasks ? <span>{tasks.length === 1 ? "1 task waiting on you" : `${tasks.length} tasks waiting on you`}</span> : null} />
      <TodoViews />
      {error ? (
        <div className="ws-state ws-state--error" role="alert">
          <h2>Your to-do could not be loaded.</h2>
          <p>{describeError(error)}</p>
        </div>
      ) : null}
      {tasks === null && !error ? (
        <p className="ws-pane__note" role="status" aria-live="polite">Loading your to-do…</p>
      ) : null}
      {tasks !== null && tasks.length === 0 ? (
        <p className="ws-hq__clear">
          Nothing is waiting on you. Decisions you can make, client replies on your deals and
          answers to what you asked appear here.
        </p>
      ) : null}
      {tasks?.length ? <section className="ws-hq" aria-label="Waiting on you"><TaskList tasks={tasks} contracts={contracts} /></section> : null}
    </div>
  );
}
