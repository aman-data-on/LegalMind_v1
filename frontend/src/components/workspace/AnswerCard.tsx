"use client";

/**
 * One change's answer card (moved out of `ChangesPane`, batch 3+4): ONE status label —
 * the row's own (`rowStatus`) — then the detail the row no longer carries (the review's
 * word, the effect for us, the kind of change), the next action for this reader, and,
 * for Legal, the label "what we told them" and the answer it prepares. Everything is
 * the server's; Legal's tie is a label only, never a decision (rule 13), and the lawyer
 * still submits every answer (AM-317 r2: no bulk answer).
 */

import { displayCaps } from "@/lib/templates";
import { useEffect, useState } from "react";

import { api, describeError } from "@/lib/api";
import {
  ACTION_LABEL, ANSWER_LABEL, ROUTE_REASON, actionsFor, clauseName, answersAsLegal, changeBucket, effectSentence, explanation,
  historyLine, readerFavour, readerStatus, readerWord, rowMeta, rowStatus, where, type Answer, type ChangeList,
  type ClientChange,
} from "@/lib/changes";
import { formatDate } from "@/lib/dates";
import type { Tie, Told } from "@/lib/dealBrief";
import { CARD_COPY, LAWYER_COPY, REOPEN_COPY, ROW_STATUS, TIE_COPY } from "@/lib/labels";
import type { Evaluation, Finding } from "@/lib/types";
import { StatusChip, chipStatus } from "@/components/StatusChip";
import { toast } from "@/components/Toast";

import { AnswerComposer, DiffText } from "./ChangeComposer";
import { EarlierAnswers } from "./ChangesBanners";
import { ForUs, Marked, answerError, rowLabel } from "./ChangesPane";
import { EscalateControl } from "./EscalateControl";
import { USER_STATUS_LABELS, requirementTitle } from "./findingLanguage";
import { IconCheck, IconClock, IconLock } from "./icons";
import { OfferLine } from "./OfferPlaybook";
import { FromOurStandard, LetteredPoints, standardSilent } from "./LawyerView";
import { AlsoInOurPaper } from "./OurPaper";
import { WordComments } from "./WordComments";

/** THE status of a change, the same words on its row and its card (one per row). */
export function RowStatus({ change, list }: { change: ClientChange; list: Parameters<typeof rowStatus>[1] }) {
  const label = rowStatus(change, list);
  // only the answered states carry an icon: a tie's label never borrows the effect arrows
  const Icon = label === ROW_STATUS.waiting ? IconClock : change.answer ? IconCheck : null;
  return (
    <span className="cx-status" data-status="" data-open={change.answer ? undefined : ""}>
      {Icon ? <Icon size={13} /> : null}{label}
    </span>
  );
}

/** The answer Legal's tie prepares: as we told them, accept theirs; further, keep ours
 *  (our standard where ours cannot be kept). Never on an answered change, and never on a
 *  measured row (round 5): there the answer writes a Legal Decision, so nothing is
 *  preselected — the lawyer chooses, the position text is still shown. */
function preparedAnswer(change: ClientChange, actions: Answer[]): Answer | null {
  if (!change.told || change.answer) return null;
  if (change.review.after.some((f) => f.evaluation_ids.length)) return null;
  const want: Answer[] = change.told.tie === "AS_TOLD" ? ["accept_theirs"] : ["keep_ours", "use_standard"];
  return want.find((a) => actions.includes(a)) ?? null;
}

/** Legal labels this change against what we told the client — a new version of that
 *  position (the server checks the right and that the row is Legal's). */
function TieControl({ change, contractId, onChanged }: { change: ClientChange; contractId: string; onChanged: () => void }) {
  const [told, setTold] = useState<Told[] | null>(null);
  const [pick, setPick] = useState(change.told?.position_key ?? "");
  const [tie, setTie] = useState<Tie>(change.told?.tie ?? "AS_TOLD");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (!open || told) return;
    let cancelled = false;
    api.dealBrief(contractId).then((b) => { if (!cancelled) setTold(b.told ?? []); },
      (cause: unknown) => { if (!cancelled) setError(describeError(cause)); });
    return () => { cancelled = true; };
  }, [open, told, contractId]);
  const write = async (p: Told, ties: Record<string, Tie>) =>
    api.tell(contractId, { text: p.text, told_on: p.told_on, ties, expected_version: p.version_number ?? 0 }, p.position_key);
  async function save(remove: boolean) {
    if (!told) return;
    setBusy(true);
    setError(null);
    try {
      const without = (p: Told) => Object.fromEntries(Object.entries(p.ties ?? {}).filter(([k]) => k !== change.row_key));
      const old = told.find((p) => p.position_key === change.told?.position_key);
      if (old && (remove || old.position_key !== pick)) await write(old, without(old));
      const chosen = told.find((p) => p.position_key === pick);
      if (!remove && chosen) await write(chosen, { ...without(chosen), [change.row_key]: tie });
      toast(remove ? TIE_COPY.removed : TIE_COPY.saved);
      onChanged();
    } catch (cause) {
      setError(describeError(cause));
      setTold(null);
    } finally {
      setBusy(false);
    }
  }
  return (
    <details className="cx-tie" onToggle={(event) => setOpen((event.target as HTMLDetailsElement).open)}>
      <summary>{TIE_COPY.title}</summary>
      {open && told === null && !error ? <p role="status" className="ws-pane__note">{CARD_COPY.loading}</p> : null}
      {told?.length === 0 ? <p className="ws-pane__note">{CARD_COPY.noneTold}</p> : null}
      {told?.length ? (
        <div className="cx-tie__form">
          <label>
            <span>{TIE_COPY.position}</span>
            <select value={pick} onChange={(e) => setPick(e.target.value)}>
              <option value="">{CARD_COPY.choose}</option>
              {told.map((p) => <option key={p.position_key} value={p.position_key}>{p.text.slice(0, 80)}</option>)}
            </select>
          </label>
          <fieldset>
            <legend className="ws-visually-hidden">{TIE_COPY.title}</legend>
            {(["AS_TOLD", "BEYOND"] as const).map((t) => (
              <label key={t}><input type="radio" name={`tie-${change.row_key}`} checked={tie === t}
                                    onChange={() => setTie(t)} /> {t === "AS_TOLD" ? TIE_COPY.asTold : TIE_COPY.beyond}</label>
            ))}
          </fieldset>
          <div className="cx-acts">
            <button type="button" className="ws-btn ws-btn--sm" disabled={busy || !pick} onClick={() => void save(false)}>{TIE_COPY.save}</button>
            {change.told ? <button type="button" className="ws-linkbtn" disabled={busy} onClick={() => void save(true)}>{TIE_COPY.remove}</button> : null}
          </div>
        </div>
      ) : null}
      {error ? <p className="cx-error" role="alert">{error}</p> : null}
    </details>
  );
}

/** The evaluations and findings a holder or an asker acts on — loaded only for the
 *  change on screen, and only when the reader can act. */
function useFindingDetails(ids: string[], wanted: boolean) {
  const [details, setDetails] = useState<{ finding: Finding; evaluations: Evaluation[] }[] | null>(null);
  const key = ids.join(",");
  useEffect(() => {
    if (!wanted || !key) return;
    let cancelled = false;
    Promise.all(key.split(",").map(async (id) => {
      const [finding, evaluations] = await Promise.all([api.finding(id), api.evaluations(id)]);
      return { finding, evaluations };
    }))
      .then((got) => { if (!cancelled) setDetails(got); })
      .catch(() => { if (!cancelled) setDetails([]); });
    return () => { cancelled = true; };
  }, [key, wanted]);
  return details;
}

export function AnswerCard({ change, list, contractId, onAnswered, onReload, inPackage, amendment = false }: {
  change: ClientChange;
  list: ChangeList;
  contractId: string;
  onAnswered: (row: Pick<ClientChange, "row_key" | "answer" | "history" | "waiting_for_approval">) => void;
  onReload: () => void;
  /** `AM-307` U2: "In the final contract: …", when this deal has one */
  inPackage?: string | null | undefined;
  /** `AM-310`: the deal is an amendment — "In the amendment: …" */
  amendment?: boolean;
}) {
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ conflict: boolean; message: string } | null>(null);
  const holder = change.route === "holder";
  const legal = answersAsLegal(list);
  // only a change worse for us goes to Legal (`AM-299`): the only one with Ask Legal
  const asking = holder && change.effect_for_us === "NEGATIVE" && list.can_answer && !legal && !change.holder_accepted;
  const actions = actionsFor(change, list);
  const details = useFindingDetails(change.review.after.map((f) => f.finding_id),
                                    holder && (list.can_decide || asking));
  const versions = { from: list.from?.version_number ?? 0, to: list.to.version_number };

  async function answer(which: Answer) {
    setBusy(true);
    setError(null);
    try {
      onAnswered(await api.answerChange(contractId, change.row_key, list.to.version_number, {
        answer: which, expected_version: change.answer?.version_number ?? 0,
        ...(reason.trim() ? { reason: reason.trim() } : {}) }));
      setReason("");
    } catch (cause) {
      setError(answerError(cause));
    } finally {
      setBusy(false);
    }
  }

  const explain = explanation(change, versions);
  // why it is routed where it is — said to whoever does not answer it themselves
  const routeWhy = change.answer || (holder && list.can_decide) ? null : ROUTE_REASON[change.route_reason];
  const given = change.answer;
  const word = readerWord(change);
  const open = change.review.after.filter((f) => f.user_status !== "ACCEPTABLE");
  const point = open[0];
  const waiting = given?.answer === "write_wording" && !!change.waiting_for_approval;
  const prepared = preparedAnswer(change, actions);
  const oneLine = legal && actions.length > 0 && standardSilent(change);

  return (
    <div className="cx-answer">
      <header className="cx-answer__head">
        <h3 title={where(change)}>{displayCaps(rowLabel(change, ""))}</h3>
        {/* batch 3+4: ONE status label for this reader, the row's own; the detail below */}
        <p className="cx-line1"><RowStatus change={change} list={list} /></p>
      </header>
      <dl className="cx-details">
        {/* U2 r4 (UI-07): "no standard" said once — for Legal here, in the grid; for the deal
            owner in the "For us" line — never a second or third time below */}
        {!word && change.route_reason !== "MEASURED_BY_A_STANDARD" && !oneLine ? null : <div><dt>{CARD_COPY.standard}</dt><dd>
          {word ? <StatusChip status={chipStatus(readerStatus(change)!, readerFavour(change))} decided={changeBucket(change) === "decided" || null} />
            : change.route_reason === "MEASURED_BY_A_STANDARD" ? CARD_COPY.covers : LAWYER_COPY.standardSilent}
          {point && requirementTitle({ code: point.requirement_code }) !== rowLabel(change, "")
            ? <span> {requirementTitle({ code: point.requirement_code })}</span> : null}
        </dd></div>}
        <div><dt>{CARD_COPY.forUs}</dt><dd><ForUs effect={change.effect_for_us} measured={change.measured} />
          {asking || oneLine ? null : <span> {effectSentence(change.effect_for_us, change.measured)}</span>}</dd></div>
        <div><dt>{CARD_COPY.change}</dt><dd>{rowMeta(change, false)}{change.moved ? CARD_COPY.moved : ""}</dd></div>
        {routeWhy && !asking ? <div><dt>{CARD_COPY.who}</dt><dd>{routeWhy}</dd></div> : null}
      </dl>
      {/* B3 p1: Legal is said ONCE — "Legal decides this one" with Ask Legal, straight
          under the heading (above the fold on a phone); no "With Legal" box as well */}
      {asking ? (
        <section className="cx-section cx-asklegal" aria-label="Ask Legal">
          {/* the one place this pane says it (PLAIN-LANGUAGE §2.4) */}
          <p className="cx-asklegal__line"><strong>{actions.includes("keep_ours")
            ? "Legal decides if you accept it; you can keep our wording." : "Legal decides this one."}</strong></p>
          {details === null && change.review.after.length ? <p role="status" className="ws-pane__note">Loading the points…</p> : null}
          {details?.length ? details.map(({ finding }) => {
            const read = change.review.after.find((f) => f.finding_id === finding.id);
            if (!read || read.user_status === "ACCEPTABLE") return null;
            return (
              <div key={finding.id} className="cx-decide__point">
                {/* named only when there are several — one point is the card's line 1 */}
                {open.length > 1 ? (
                  <p className="cx-decide__name">
                    <StatusChip status={chipStatus(read.user_status, read.in_our_favour)} /> {requirementTitle({ code: read.requirement_code })}
                  </p>
                ) : null}
                <EscalateControl finding={finding} onChanged={onReload} />
              </div>
            );
          }) : null}
        </section>
      ) : null}
      {/* nothing confirmed which clause holds this point: say so, never pick one */}
      {!change.after && change.candidates?.length ? (
        <p className="ws-pane__note">We could not tell which clause covers this. Clauses that may:{" "}
          {change.candidates.map(clauseName).filter(Boolean).join("; ")}.</p>
      ) : null}
      {/* AM-305: the playbook line this change is measured by */}
      <OfferLine change={change} contractId={contractId} />

      {/* On a narrow screen the passage column is not shown, so the card carries it. */}
      {/* the passage and its comments: the phone's copy (the passage column shows them on a
          wide screen), so a comment is drawn once at any width */}
      <div className="cx-answer__passage" tabIndex={0} role="region" aria-label="The changed passage"><Marked change={change} list={list} />
        <WordComments comments={[...(change.after?.comments ?? []), ...(change.before?.comments ?? [])]} /></div>
      <EarlierAnswers change={change} />

      {given ? <GivenAnswer change={change} waiting={waiting} /> : null}
      {given?.auto && list.can_decide && list.replied_in == null ? (
        <section className="cx-reopen" aria-label={REOPEN_COPY.title}>
          <label className="cx-reason">
            <span>{REOPEN_COPY.reason}</span>
            <input type="text" maxLength={200} value={reason} onChange={(event) => setReason(event.target.value)} />
          </label>
          <div className="cx-acts">
            <button type="button" className="ws-btn ws-btn--sm" disabled={busy || !reason.trim()}
                    onClick={() => void answer("keep_ours")}>{REOPEN_COPY.button}</button>
          </div>
          {error ? <p className="cx-error" role="alert">{error.message}</p> : null}
        </section>
      ) : null}
      {inPackage ? <p className="cx-inpkg"><strong>{amendment ? "In the amendment:" : "In the final contract:"}</strong> {inPackage}</p> : null}

      {change.review.after.length > 1 || change.review_delta.length ? (
        <div className="cx-review">
          {change.review.after.length > 1 ? (
            <>
              <span className="cx-label">From the review of version {versions.to}</span>
              <ul>
                {change.review.after.map((f) => (
                  <li key={f.finding_id}><StatusChip status={chipStatus(f.user_status, f.in_our_favour)} /> {requirementTitle({ code: f.requirement_code })}</li>
                ))}
              </ul>
            </>
          ) : null}
          {change.review_delta.length && list.from ? (
            <>
              <span className="cx-label">Since version {versions.from}</span>
              <ul>
                {change.review_delta.map((d) => (
                  <li key={d.requirement_code}>
                    {requirementTitle({ code: d.requirement_code })}: {d.before ? USER_STATUS_LABELS[d.before] : "not measured"} →{" "}
                    {d.after ? USER_STATUS_LABELS[d.after] : "not measured"}
                  </li>
                ))}
              </ul>
            </>
          ) : null}
        </div>
      ) : null}
      <AlsoInOurPaper contractId={contractId} clause={change.clause.number} />
      <LetteredPoints change={change} />
      {legal && actions.length ? <FromOurStandard change={change} /> : null}
      {change.triage?.reasons.length ? (
        <ul className="cx-reasons">
          {change.triage.reasons.map((r, i) => <li key={i}>{r.reason}</li>)}
        </ul>
      ) : null}

      {legal && holder && list.can_answer && list.can_decide ? <TieControl change={change} contractId={contractId} onChanged={onReload} /> : null}
      {legal && actions.length ? (
        <>
          {/* batch 3+4: the answer prepared from Legal's own tie — the lawyer still submits */}
          {change.told && !change.answer ? <p className="cx-prepared"><span className="cx-label">{prepared ? TIE_COPY.why : TIE_COPY.title}</span> &ldquo;{change.told.text}&rdquo;</p> : null}
          <AnswerComposer change={change} list={list} actions={actions} contractId={contractId}
                          details={details} onAnswered={onAnswered} onReload={onReload}
                          initial={prepared} />
        </>
      ) : null}

      {/* AB-213 D10: a change Legal answers carries no verdict control for sales until
          Legal has accepted it — sales sends it to Legal, never answers it first */}
      {!legal && actions.length && !(holder && !change.holder_accepted) ? (
        <section className="cx-section" aria-label={given ? "Change your answer" : "Your answer"}>
          <h4 className="cx-label">{given ? "Change your answer" : "Your answer"}</h4>
          {change.route === "favour" && change.favour_reason ? <p className="cx-favour">{change.favour_reason}</p> : null}
          <div className="cx-acts">
            {actions.map((a) => (
              <button key={a} type="button"
                      className={`ws-btn ws-btn--sm${change.route === "favour" && a === "accept_theirs" ? " ws-btn--primary" : ""}`}
                      disabled={busy || error?.conflict} onClick={() => void answer(a)}>
                {holder && a === "accept_theirs" ? "Accept their wording — Legal has accepted it" : ACTION_LABEL[a]}
              </button>
            ))}
          </div>
          <label className="cx-reason">
            <span>Reason <span className="cx-reason__opt">(optional, one line)</span></span>
            <input type="text" maxLength={200} value={reason}
                   onChange={(event) => setReason(event.target.value)} />
          </label>
          {error ? (
            <p className="cx-error" role="alert">
              {error.message}{" "}
              {error.conflict ? <button type="button" className="ws-escalate__link" onClick={onReload}>Reload</button> : null}
            </p>
          ) : null}
        </section>
      ) : null}

      {change.history.length > 1 ? (
        <p className="cx-history"><span className="cx-label">History</span> {historyLine(change.history)}</p>
      ) : null}
      {explain.length ? (
        <details className="cx-explain">
          <summary>Why does this matter?</summary>
          <ul>{explain.map((line, i) => <li key={i}>{line}</li>)}</ul>
        </details>
      ) : null}
    </div>
  );
}

/** The answer on record: what, who and when, the wording it carries and its notes. The
 *  internal note is drawn only when the server sent its key (`AM-285` r3, omitted else). */
function GivenAnswer({ change, waiting }: { change: ClientChange; waiting: boolean }) {
  const given = change.answer!;
  return (
    <div className="cx-given" role="status" id={`cx-given-${change.row_key}`} tabIndex={-1}>
      <p className="cx-given__line">
        {waiting ? <IconClock size={14} /> : <IconCheck size={14} />}
        <span>
          <strong>{ANSWER_LABEL[given.answer].replace(/^./, (c) => c.toUpperCase())}</strong>
          {" "}— {[given.decided_by, formatDate(given.decided_at)].filter(Boolean).join(", ")}
          {given.reason ? <span className="cx-given__why">&ldquo;{given.reason}&rdquo;</span> : null}
        </span>
      </p>
      {waiting ? (
        <p className="cx-waiting">
          Your wording is recorded as a Legal Decision. It takes effect when a second person with the
          right approves it — needed on a contract you own or created, or where our
          standard asks for two. The reply cannot be prepared until then.
        </p>
      ) : null}
      {given.wording ? (
        <div className="cx-given__wording">
          <span className="cx-label">Our wording, against theirs</span>
          <DiffText from={change.after?.text ?? ""} to={given.wording} added="we add" removed="we remove"
                    labels={{ from: "Their wording", to: "Our wording" }} />
        </div>
      ) : null}
      {given.client_note ? (
        <p className="cx-note-read cx-note-read--client"><span>Sent to the client</span>{given.client_note}</p>
      ) : null}
      {given.internal_note ? (
        <p className="cx-note-read cx-note-read--internal"><span><IconLock size={12} /> Only Legal sees this — never sent</span>{given.internal_note}</p>
      ) : null}
    </div>
  );
}

