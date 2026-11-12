"use client";

/**
 * The To-do's views (`AM-264`): My to-do, and — for whoever works them — the Reviews and
 * Legal queues, whose screens are unchanged. A strip of links, so each view keeps its own
 * address; gating is presentation only (rule 18), the server scopes every list.
 *
 * The person's home queue and the To-do are ONE task list (`AM-291`): the server's items,
 * one per contract (`oneTaskPerContract`). Nothing here filters by role name or decides.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { taskAction } from "@/lib/nextStep";
import { useSession } from "@/lib/session";
import type { Contract, Counterparty, TodoItem } from "@/lib/types";
import { TemplatesToApprove } from "@/components/templates/TemplateList";

import { contractFacts, oneTaskPerContract, personaFor, relativeTime, todoViews } from "./model";

export function TodoViews() {
  const { can } = useSession();
  const pathname = usePathname();
  const views = todoViews(can);
  if (views.length < 2) return null;
  return (
    <nav className="lm-tabs" aria-label="To-do views">
      {views.map((view) => (
        <Link key={view.href} href={view.href}
              aria-current={pathname === view.href ? "page" : undefined}>
          {view.label}
        </Link>
      ))}
    </nav>
  );
}

/** One task (`AM-291`): the server's sentence, then what tells this contract apart —
 *  its name, client, type, version and upload time, reference — how long it has waited,
 *  and the act in the header's own words (`taskAction`). The home and the To-do both. */
export function TaskRow({ item, contract, client }: {
  item: TodoItem; contract?: Contract | undefined; client?: string | null | undefined;
}) {
  const action = taskAction(item);
  const facts = contract ? contractFacts(contract, client) : [];
  return (
    <li className="ws-hq__item">
      {/* the contract leads — several rows can say "3 points await your decision" — then
          what waits, then the facts that tell it apart */}
      <span className="ws-hq__what">
        <span className="ws-hq__sentence">{item.contract_name}</span>
        <span className="ws-hq__said">{item.sentence}</span>
        {facts.length ? (
          <span className="ws-hq__doc">
            {facts.map((part) => <span key={part}>{part}</span>)}
          </span>
        ) : null}
      </span>
      <span className="ws-hq__since" title={item.since ?? undefined}>{relativeTime(item.since)}</span>
      <Link className="ws-btn ws-hq__act" href={item.link} aria-label={`${action}: ${item.contract_name}`}>
        {action}
      </Link>
    </li>
  );
}

/** The person's tasks, ONE per contract, loaded once — the home's queue and the To-do page
 *  render the same list, so the two can never disagree on a count. */
export function useTasks(): { tasks: TodoItem[] | null; contracts: Map<string, Contract>; error: unknown; reload: () => void } {
  const [tasks, setTasks] = useState<TodoItem[] | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [contracts, setContracts] = useState<Map<string, Contract>>(new Map());
  const [error, setError] = useState<unknown>(null);
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const list = oneTaskPerContract((await api.todo()).items);
        if (cancelled) return;
        setTasks(list);
        // ponytail: one detail request per task; a by-ids list endpoint if queues grow
        const got = await Promise.all(list.map((i) => api.contract(i.contract_id).catch(() => null)));
        if (!cancelled) setContracts(new Map(got.filter((c): c is Contract => !!c).map((c) => [c.id, c])));
      } catch (cause) {
        if (!cancelled) setError(cause);
      }
    })();
    return () => { cancelled = true; };
  }, [attempt]);
  const reload = () => { setError(null); setTasks(null); setAttempt((n) => n + 1); };
  return { tasks, contracts, error, reload };
}

export function TaskList({ tasks, contracts, companies = [] }: {
  tasks: TodoItem[]; contracts: Map<string, Contract>; companies?: Counterparty[];
}) {
  const client = (c?: Contract) => companies.find((co) => co.id === c?.counterparty_id)?.name;
  return (
    <ul className="ws-hq__list">
      {tasks.map((item) => {
        const contract = contracts.get(item.contract_id);
        return <TaskRow key={`${item.kind}:${item.contract_id}`} item={item} contract={contract}
                        client={client(contract)} />;
      })}
    </ul>
  );
}

/** The home's queue: the same tasks as the To-do, under the person's own heading —
 *  "For my review" is the lawyer's page title already, so it is not said twice. The page
 *  loads the tasks once (`useTasks`) and shares them with the list's turn marker. */
export function HomeQueue({ companies, todo }: {
  companies: Counterparty[]; todo: ReturnType<typeof useTasks>;
}) {
  const { can } = useSession();
  const legal = personaFor(can) === "legal";
  const { tasks, contracts } = todo;
  if (tasks === null) return null;
  return (
    <>
      <section className="ws-hq" {...(legal ? { "aria-label": "For my review" } : { "aria-labelledby": "ws-home-turn" })}>
        {legal ? null : (
          <h2 id="ws-home-turn" className="ws-home__qtitle">
            Your turn<span className="ws-home__qn">{tasks.length}</span>
          </h2>
        )}
        {tasks.length ? <TaskList tasks={tasks} contracts={contracts} companies={companies} />
          : <p className="ws-hq__clear">{legal ? "Nothing is waiting for your review." : "Nothing is waiting on you."}</p>}
      </section>
      <TemplatesToApprove />
    </>
  );
}
