"use client";

/**
 * New contract (S5, flow 1 "Sales creates") — our NDA or MSA for a client from a PUBLISHED
 * template (`AM-282` r4 / `AM-283`), in three steps: what and who, the details beside the
 * live contract, review and create. The answers live on the server as a draft
 * (`AM-295`): every save sends `expected_version`; a 409 means another tab saved first.
 * The created v1 is reviewed by the same engine as any upload — this page decides nothing.
 */

import { DOCUMENT_FACES, useStartFaces } from "@/components/workspace/faces";
import { PageHeader } from "@/components/page/PageHeader";
import { ACTION, CONVERT_COPY, INTAKE_COPY as C } from "@/lib/labels";
import Link from "@/components/AppLink";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api, ApiError, describeError } from "@/lib/api";
import type { ClientChecklist } from "@/lib/clientDetails";
import {
  OURS, answered, checkWords, splitPoints, display, groups, outsideRange, problemWords, profileValue,
  askedNow, toAnswers, unanswered,
  type Answers, type Draft, type DraftCheck, type DraftPreview, type FieldProblem, type PublishedTemplate, type Question,
} from "@/lib/newContract";
import { cardName, type TemplateCardData } from "@/lib/templates";
import type { Counterparty } from "@/lib/types";
import { ErrorState } from "@/components/Feedback";
import { requirementTitle } from "@/components/workspace/findingLanguage";

import { CertificateView } from "./CertificateView";
import { ClientDetailsCard } from "./ClientDetailsCard";
import { ContractPreview } from "./ContractPreview";
import { IntakeSteps, type IntakeStep } from "./IntakeSteps";
import { OurCompany } from "./OurCompany";
import { QuestionField, questionId, type ProfileLink } from "./QuestionField";
import { StepOne } from "./StepOne";
import { StillNeeded } from "./StillNeeded";
import "./newcontract.css";
import "./intake.css";
import { toastFailure } from "@/components/Toast";

export { StepOne };
/** The draft's steps in the address (`?step=`): 2 client details, 3 this deal, 4 review. */
const STEP_PARAM: Record<2 | 3 | 4, string> = { 2: "client", 3: "deal", 4: "review" };

type SaveState = "idle" | "saving" | "saved" | "conflict" | "error";

/** One save: the answers with the version they were read at. A stale version is a 409 —
 *  the draft was saved elsewhere, and nothing here may overwrite it. */
export async function saveOnce(id: string, answers: Answers, version: number,
                               save = api.saveDraft): Promise<
  { kind: "saved"; draft: Draft } | { kind: "conflict" } | { kind: "error"; message: string }> {
  try {
    return { kind: "saved", draft: await save(id, answers, version) };
  } catch (e) {
    if (e instanceof ApiError && e.isConflict) return { kind: "conflict" };
    return { kind: "error", message: describeError(e) };
  }
}

/** No published template for this type and brand: say why in plain words, and what to do. */
export function NoTemplate({ reason, approver, onUpload }: { reason: string; approver: boolean; onUpload: () => void }) {
  return (
    <div className="nc-blocked" role="status">
      <p className="nc-blocked__why">{reason}</p>
      <p className="nc-quiet">You can upload a contract instead, or come back once it is published.</p>
      <div className="nc-actions nc-actions--start">
        <button type="button" className="ws-btn" onClick={onUpload}>{C.uploadInstead}</button>
        {approver ? <Link className="nc-link" href="/templates">Open Templates</Link> : null}
      </div>
    </div>
  );
}

export function ConflictBanner({ onReload }: { onReload: () => void }) {
  return (
    <div className="nc-conflict" role="alert">
      <p>These answers were saved in another tab or window. Reload them to carry on. What you typed here since the last save is not kept.</p>
      <button type="button" className="ws-btn ws-btn--sm" onClick={onReload}>Reload the answers</button>
    </div>
  );
}

const SAVE_WORDS: Record<SaveState, string> = {
  // a conflict is said once, by its banner beside the answers
  idle: "", saving: "Saving…", saved: "Saved", conflict: "", error: "Not saved",
};

// ---------------------------------------------------------------- steps 2 to 4
/** The early check's answer for one saved version of the draft. */
type Checked = { version: number; check: DraftCheck | null };
type Panel = "needed" | "certificate" | "contract";

function Drafting({ draftId, step, published, setStep, convertFor = null }: {
  draftId: string;
  /** S5: the client-paper deal these answers convert; Create goes back to it */
  convertFor?: string | null;
  step: 2 | 3 | 4;
  published: PublishedTemplate[];
  setStep: (s: 2 | 3 | 4) => void;
}) {
  const router = useRouter();
  const [draft, setDraft] = useState<Draft | null>(null);
  const [local, setLocal] = useState<Answers>({});
  const [preview, setPreview] = useState<DraftPreview | null>(null);
  const [client, setClient] = useState<Counterparty | null>(null);
  const [checklist, setChecklist] = useState<ClientChecklist | null>(null);
  const [save, setSave] = useState<SaveState>("idle");
  const [fresh, setFresh] = useState<string | null>(null);
  const [view, setView] = useState<"form" | Panel>("form");
  // the tab the reader chose, on the step they chose it (each step opens on its own default)
  const [panel, setPanel] = useState<{ step: number; tab: Panel } | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [createProblems, setCreateProblems] = useState<FieldProblem[]>([]);
  const [refused, setRefused] = useState(false);
  const [replaced, setReplaced] = useState(false);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [oursOpen, setOursOpen] = useState(false);
  const [profileState, setProfileState] = useState<Record<string, ProfileLink["state"]>>({});
  const [checked, setChecked] = useState<Checked | null>(null);

  const version = useRef(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inflight = useRef<Promise<void> | null>(null);
  const pending = useRef(false);
  const localRef = useRef<Answers>({});
  const conflict = useRef(false);

  const template = draft ? published.find((t) => t.id === draft.template_version_id) : undefined;
  const questions = useMemo(() => template?.questions ?? [], [template]);
  // batch 7: on an MSA the client's facts are the card's (read from the client record)
  const owned = useMemo(() => new Set(checklist?.applies ? checklist.questions ?? [] : []), [checklist]);
  const dealQuestions = useMemo(() => questions.filter((q) => !owned.has(q.key)), [questions, owned]);

  const refreshPreview = useCallback(() => {
    api.draftPreview(draftId).then(setPreview).catch(toastFailure("The preview could not be updated"));
  }, [draftId]);
  const refreshChecklist = useCallback(() => {
    api.draftClientDetails(draftId).then(setChecklist).catch(toastFailure("The client details could not be loaded"));
  }, [draftId]);

  const apply = useCallback((d: Draft) => {
    version.current = d.version;
    conflict.current = false;
    localRef.current = d.answers;
    setDraft(d); setLocal(d.answers); setSave("idle");
    refreshPreview(); refreshChecklist();
    if (d.counterparty_id) api.counterparty(d.counterparty_id).then(setClient).catch(toastFailure("The client’s details could not be loaded"));
    if (d.template_status !== "PUBLISHED") setReplaced(true);
  }, [refreshPreview, refreshChecklist]);

  const reload = useCallback(() => {
    api.draft(draftId).then(apply).catch((e) => setFailure(e instanceof ApiError && e.isNotFound
      ? "This draft is not here any more. Drafts are kept for 30 days; start a new contract."
      : describeError(e)));
  }, [draftId, apply]);

  useEffect(() => { reload(); }, [reload]);

  const flush = useCallback(async (): Promise<void> => {
    if (conflict.current) return;
    if (inflight.current) { pending.current = true; return inflight.current; }
    setSave("saving");
    const run = (async () => {
      do {               // a change typed while a save was in flight is saved after it
        pending.current = false;
        const r = await saveOnce(draftId, toAnswers(dealQuestions, localRef.current), version.current);
        if (r.kind === "saved") {
          version.current = r.draft.version;
          setDraft(r.draft); setSave("saved");
          refreshPreview(); refreshChecklist();
        } else {
          if (r.kind === "conflict") { conflict.current = true; setSave("conflict"); }
          else { setSave("error"); setFailure(r.message); }
          return;
        }
      } while (pending.current);
    })();
    inflight.current = run;
    await run;
    inflight.current = null;
  }, [draftId, dealQuestions, refreshPreview, refreshChecklist]);

  function change(key: string, value: unknown) {
    localRef.current = { ...localRef.current, [key]: value };
    setLocal(localRef.current);
    setFresh(key);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => void flush(), 600);
  }

  /** the client record changed in the card: the contract reads it, so draw both again */
  function onClient(c: Counterparty) { setClient(c); refreshChecklist(); reload(); }

  function focusLater(id: string) {
    requestAnimationFrame(() => requestAnimationFrame(() => {
      const el = document.getElementById(id);
      if (!el) return;
      el.scrollIntoView({ block: "center", behavior: "smooth" });
      const target = el.matches("fieldset") ? el.querySelector<HTMLElement>("input:checked, input") : el;
      (target ?? el).focus({ preventScroll: true });
    }));
  }
  function jump(key: string) {
    // a client fact the card owns: its field on step 2 (benchmark 1: a blank goes to its question)
    if (owned.has(key)) { toClientItem(questions.find((q) => q.key === key)?.profile_field ?? "line_of_business"); return; }
    if (step !== 3) setStep(3);
    setView("form");
    if (questions.find((q) => q.key === key)?.group === OURS) setOursOpen(true);
    focusLater(questionId(key));
  }
  function toClientItem(field: string) {
    if (step !== 2) setStep(2);
    setView("form");
    focusLater(field === "check" ? "ic-g-check" : field === "gst_certificate" ? "ic-g-certificate" : `ic-f-${field}`);
  }

  const clientRecord = client as unknown as Record<string, unknown> | null;
  function profileLink(q: Question): ProfileLink | undefined {
    if (!q.profile_field || !client) return undefined;
    const field = q.profile_field;
    return {
      value: profileValue(clientRecord, q), state: profileState[q.key],
      onUpdate: () => {
        const typed = String(local[q.key] ?? "").trim();
        setProfileState((s) => ({ ...s, [q.key]: "saving" }));
        api.updateCounterparty(client.id, { [field]: typed })
          .then((c) => { setClient(c); setProfileState((s) => ({ ...s, [q.key]: "saved" })); })
          .catch(() => setProfileState((s) => ({ ...s, [q.key]: "error" })));
      },
    };
  }

  const left = unanswered(dealQuestions, local);
  const blocked = save === "conflict";
  // the early check: on the review step, once every required detail is in and saved
  const checkable = step === 4 && !!draft && !left.length && save !== "saving" && !blocked && !creating;
  const savedVersion = draft?.version;
  useEffect(() => {
    if (!checkable || savedVersion === undefined) return;
    let live = true;
    api.draftCheck(draftId)
      .then((c) => { if (live) setChecked({ version: savedVersion, check: c }); })
      .catch(() => { if (live) setChecked({ version: savedVersion, check: null }); });
    return () => { live = false; };
  }, [checkable, savedVersion, draftId]);
  const check = checked && checked.version === savedVersion ? checked : null;

  async function create() {
    setCreating(true); setFailure(null); setCreateProblems([]);   // first: a second click finds it disabled
    if (timer.current) clearTimeout(timer.current);
    try {
      await flush();
      if (conflict.current || !draft) { setCreating(false); return; }
      if (convertFor) {        // S5: the deal's Changes tab makes our paper from these answers
        router.push(`/contracts/${encodeURIComponent(convertFor)}/changes?convert_draft=${encodeURIComponent(draftId)}`);
        return;
      }
      const made = await api.createFromDraft(draftId, version.current, name.trim() || undefined);
      router.push(`/contracts/${made.contract_id}`);
    } catch (e) {
      setCreating(false);
      if (e instanceof ApiError && e.code === "TEMPLATE_NOT_PUBLISHED") setReplaced(true);
      else if (e instanceof ApiError && e.code === "CLIENT_DETAILS_INCOMPLETE") {
        setRefused(true); refreshChecklist();                  // batch 7: the server's gate
        requestAnimationFrame(() => document.getElementById("ic-refused")?.focus());
      } else if (e instanceof ApiError && e.fieldProblems?.length) setCreateProblems(e.fieldProblems);
      else if (e instanceof ApiError && e.isConflict) { conflict.current = true; setSave("conflict"); }
      else setFailure(describeError(e));
    }
  }

  if (failure && !draft) {
    return <div className="nc-one"><p className="nc-error" role="alert">{failure}</p>
      <Link className="ws-btn" href="/contracts/new">Start a new contract</Link></div>;
  }
  if (!draft) return <div className="lm-page"><LoadingRows /></div>;
  if (!template || replaced) {
    return (
      <div className="nc-one nc-blocked" role="status">
        <p className="nc-blocked__why">Legal replaced this template while you worked.</p>
        <p className="nc-quiet">Start again from the published version. This draft is kept for 30 days.</p>
        <div className="nc-actions nc-actions--start"><Link className="ws-btn ws-btn--primary" href="/contracts/new">Start again</Link></div>
      </div>
    );
  }

  const serverProblem = new Map((draft.problems ?? []).filter((p) => p.problem !== "is required").map((p) => [p.field, p.problem]));
  const asked = new Set(left.map((q) => q.key));
  const otherProblems = [...createProblems, ...draft.problems.filter((p) => p.problem !== "is required" && !owned.has(p.field))]
    .filter((p, i, all) => !asked.has(p.field) && all.findIndex((x) => x.field === p.field && x.problem === p.problem) === i);
  const ownProblems = dealQuestions.filter((q) => outsideRange(q, local[q.key]));
  const ready = !left.length && !otherProblems.length && !ownProblems.length && !blocked;
  const title = cardName(template);
  const shownGroups = groups(dealQuestions, local);
  const fromProfile = dealQuestions.filter((q) => {
    const v = profileValue(clientRecord, q);
    return v != null && String(local[q.key] ?? "").trim() === v.trim();
  }).length;
  const card = checklist?.applies && client ? checklist : null;
  const asking = askedNow(dealQuestions, local);
  const clientLeft = card ? card.items.filter((i) => i.n > 1 && (i.status === "missing" || i.status === "fix")) : [];
  const unchecked = !!card && !!card.verify_needed && !card.verified;

  const next = step === 4 ? (
    <button type="button" className="ws-btn ws-btn--primary" disabled={!ready || creating} onClick={() => void create()}>
      {creating ? "Creating…" : convertFor ? CONVERT_COPY.convert : ACTION.createContract}
    </button>
  ) : (
    <button type="button" className="ws-btn ws-btn--primary" disabled={blocked}
            onClick={() => { void flush(); setStep((step + 1) as 3 | 4); setView("form"); }}>{C.continue}</button>
  );
  const back = step === 2 || (step === 3 && !card)
    ? <Link className="ws-btn" href={`/contracts/new${convertFor ? `?convert=${encodeURIComponent(convertFor)}` : ""}`}>{C.back}</Link>
    : <button type="button" className="ws-btn" onClick={() => setStep((step - 1) as 2 | 3)}>{C.back}</button>;

  const head = (
    <PageHeader wide title="New contract" back={{ href: "/contracts", label: "Contracts" }}
      meta={<>
        <span>{cardName(template)}{client ? ` for ${client.name}` : ""}</span>
      </>} />
  );

  const field = (q: Question) => (
    <QuestionField key={q.key} q={q} value={local[q.key]} problem={serverProblem.get(q.key)}
                   profile={card ? undefined : profileLink(q)} onChange={change} />
  );

  const form = (
    <div className="nc-form">
      {blocked ? <ConflictBanner onReload={reload} /> : null}
      <h2 className="ic-card__title">{C.dealTitle}</h2>
      {fromProfile && !card ? <p className="nc-note">{fromProfile} answer{fromProfile === 1 ? "" : "s"} filled in from {client?.name ?? "the client"}&rsquo;s profile. Check them; a change can be saved back to the profile.</p> : null}
      {shownGroups.map((g) => g.name === OURS ? (
        <OurCompany key={g.name} questions={g.questions} local={local} open={oursOpen} onOpen={setOursOpen}>
          {g.questions.filter((q) => q.role !== "our_name").map(field)}
        </OurCompany>
      ) : (
        <section key={g.name} className="nc-group" aria-labelledby={`nc-g-${g.name}`}>
          <h3 id={`nc-g-${g.name}`} className="nc-sub">{g.name}</h3>
          {g.questions.map(field)}
        </section>
      ))}
    </div>
  );

  const points = check?.check?.points ?? [];
  // AM-316: what the template sends on every deal, apart from what the answers moved
  const { fromTemplate, fromDetails } = splitPoints(points, template.known_points);
  const pointList = (list: typeof points) => (
    <ul className="nc-check__list">
      {list.map((p) => (
        <li key={p.code}><span className="nc-item__l1">{requirementTitle({ code: p.code, name: p.name })}</span>
          <span className="nc-item__l2">{checkWords(p.classification)}</span></li>
      ))}
    </ul>
  );
  const review = (
    <div className="nc-form nc-review">
      {blocked ? <ConflictBanner onReload={reload} /> : null}
      <h2 className="ic-card__title">{C.steps[3]}</h2>
      {card && (clientLeft.length > 3) ? (
        <section id="ic-refused" tabIndex={-1} className="ic-summary" data-refused={refused || undefined} aria-labelledby="ic-refused-t">
          <h3 id="ic-refused-t" className="nc-sub">{C.refusedTitle}</h3>
          <button type="button" className="nc-linkbtn" onClick={() => toClientItem("gst_certificate")}>
            {C.clientOpen(clientLeft.length)}{unchecked ? `. ${C.notChecked}` : ""}</button>
        </section>
      ) : card && (clientLeft.length || unchecked) ? (
        <section id="ic-refused" tabIndex={-1} className="ic-summary" data-refused={refused || undefined} aria-labelledby="ic-refused-t">
          <h3 id="ic-refused-t" className="nc-sub">{C.refusedTitle}</h3>
          <p className="ic-quiet">{C.refusedLead}</p>
          <ul>
            {clientLeft.map((i) => (
              <li key={i.key}><button type="button" className="nc-linkbtn" onClick={() => toClientItem(i.profile_field ?? i.key)}>
                {C.items[i.key]}</button></li>
            ))}
            {unchecked ? <li><button type="button" className="nc-linkbtn" onClick={() => toClientItem("check")}>{C.checkLine}</button></li> : null}
          </ul>
        </section>
      ) : null}
      <div className="nc-sum nc-template">
        <dl><div><dt>Template</dt><dd>{cardName(template)}, version {template.version}</dd></div></dl>
        <p className="nc-quiet">To use another template, start a new contract. These answers are kept for 30 days.</p>
      </div>
      {left.length || otherProblems.length || ownProblems.length ? (
        <section aria-labelledby="nc-left">
          <h3 id="nc-left" className="nc-sub nc-sub--small">Still to fill in <span>{left.length + otherProblems.length + ownProblems.length}</span></h3>
          <ul className="nc-left">
            {[...left, ...ownProblems].map((q) => (
              <li key={q.key}><button type="button" className="nc-item nc-item--link" onClick={() => jump(q.key)}>
                <span className="nc-item__l1">{q.label}: {left.includes(q) ? "required" : "outside our template"}</span>
                <span className="nc-item__l2">{q.group ?? "Details"}</span>
              </button></li>
            ))}
            {otherProblems.map((p) => {
              const w = problemWords(p, questions);
              return (
                <li key={`${p.field}-${p.problem}`}>{w.key ? (
                  <button type="button" className="nc-item nc-item--link" onClick={() => jump(w.key!)}>
                    <span className="nc-item__l1">{w.text}</span><span className="nc-item__l2">Go to the question</span>
                  </button>
                ) : <p className="nc-item nc-item--static"><span className="nc-item__l1">{w.text}</span></p>}</li>
              );
            })}
          </ul>
        </section>
      ) : <p className="nc-ok">{card ? C.dealComplete : "Every required detail is filled in."}</p>}

      <section aria-labelledby="nc-legal" className="nc-check">
        <h3 id="nc-legal" className="nc-sub nc-sub--small">What goes to Legal</h3>
        {left.length ? (
          <p className="nc-quiet">Fill in the details above to see which points will go to Legal.</p>
        ) : !check ? (
          <p className="nc-quiet nc-check__busy" role="status">Reading the contract against our standards… You can create it without waiting.</p>
        ) : !check.check ? (
          <p className="nc-quiet" role="status">The early check could not run. You can still create the contract; our review reads it either way.</p>
        ) : !check.check.ready ? (
          <p className="nc-quiet">Fill in the details above to see which points will go to Legal.</p>
        ) : points.length ? (
          <>
            <p className="nc-check__lead">These {points.length} point{points.length === 1 ? "" : "s"} will go to Legal before the contract can be sent:</p>
            {fromTemplate.length ? <>
              <h4 className="nc-check__from">From this template, on every deal ({fromTemplate.length})</h4>
              {pointList(fromTemplate)}
            </> : null}
            {fromDetails.length ? <>
              <h4 className="nc-check__from">From your details ({fromDetails.length})</h4>
              {pointList(fromDetails)}
            </> : null}
            <p className="nc-quiet">You can still create it now. Legal decides each point; nothing here is decided.</p>
          </>
        ) : (
          <p className="nc-check__lead">Nothing here differs from our standards. Once our review confirms it, it is ready to send.</p>
        )}
      </section>

      <section aria-labelledby="nc-answers">
        <h3 id="nc-answers" className="nc-sub nc-sub--small">Your answers</h3>
        {shownGroups.map((g) => (
          <div key={g.name} className="nc-sum">
            <div className="nc-sum__head">
              <h4>{g.name}</h4>
              <button type="button" className="nc-linkbtn" onClick={() => jump(g.questions[0]!.key)}
                      aria-label={`Edit ${g.name}`}>Edit</button>
            </div>
            <dl>
              {g.questions.filter((q) => (q.class ?? "M") !== "O" || answered(q, q.locked_value ?? local[q.key])).map((q) => {
                const v = q.locked_value ?? local[q.key];
                return (
                  <div key={q.key}><dt>{q.label}</dt>
                    <dd>{answered(q, v) ? display(q, v) : <span className="nc-quiet">Not filled in</span>}</dd></div>
                );
              })}
            </dl>
          </div>
        ))}
      </section>

      <div className="nc-q">
        <label className="nc-q__label" htmlFor="nc-name">Name in LegalMind<span className="nc-q__req">Optional</span></label>
        <p className="nc-q__help" id="nc-name-help">How the contract is listed here. The client never sees it.</p>
        <input id="nc-name" type="text" aria-describedby="nc-name-help" value={name} placeholder={`${title}${client ? ` — ${client.name}` : ""}`}
               onChange={(e) => setName(e.target.value)} />
      </div>
      <p className="nc-explain">
        When you create it, our review reads it against our standards, as it does any contract. Anything outside our
        standard goes to Legal before it can be sent.
      </p>
      {failure ? <p className="nc-error" role="alert">{failure}</p> : null}
      {creating ? <p className="nc-quiet" role="status">Creating the contract and starting our review…</p> : null}
    </div>
  );

  // the panel: step 2 opens on what is still needed (the certificate beside it), 3 and 4 on the contract
  // one fixed order; the step chooses which opens (step 2: what is left, 3 and 4: the contract)
  const tabs: Panel[] = card ? ["needed", "certificate", "contract"] : ["contract"];
  const shownPanel = panel?.step === step && tabs.includes(panel.tab) ? panel.tab : step === 2 ? tabs[0]! : "contract";
  const stillNeeded = (
    <StillNeeded checklist={card} dealLeft={left} dealAsked={asking.length} refused={refused}
                 dealDone={asking.filter((q) => answered(q, local[q.key])).length}
                 onClientItem={toClientItem} onQuestion={jump} />
  );
  const panels: Record<Panel, React.ReactNode> = {
    needed: stillNeeded,
    certificate: client ? <CertificateView clientId={client.id} filename={client.gst_certificate?.filename}
                                           uploadedAt={client.gst_certificate?.uploaded_at} /> : null,
    contract: (
      <div className="ic-sheet">
        <p className="nc-well__note">The wording is fixed by our template. Only your answers change it.</p>
        {preview?.model ? (
          <ContractPreview model={preview.model} questions={questions} local={local} fresh={fresh} onJump={jump} />
        ) : <p className="nc-quiet">{preview ? "The preview could not be drawn yet." : "Drawing the contract…"}</p>}
      </div>
    ),
  };
  const main = step === 2 && card && client
    ? <ClientDetailsCard client={client} checklist={card} refused={refused} onClient={onClient} />
    : step === 4 ? review : form;

  return (
    <div className="lm-page ic" data-view={view}>
      {head}
      <IntakeSteps step={step} onGo={(s) => (s === 1 ? router.push("/contracts/new") : setStep(s as 2 | 3 | 4))}
                   done={{ 1: true, 2: !!card?.client_ready || !card, 3: !left.length }}
                   notes={{ 2: card?.counts ? (card.client_ready ? C.onFile : card.counts.done === card.counts.needed && card.verify_needed
                              ? C.addedNotChecked(card.counts.done, card.counts.needed) : C.added(card.counts.done, card.counts.needed)) : undefined,
                            3: C.answered(asking.length - left.length, asking.length) }} />
      <div className="ic-tabs ic-tabs--phone" role="group" aria-label="Show">
        {(["form", ...tabs] as const).map((t) => (
          <button key={t} type="button" aria-pressed={view === t} onClick={() => setView(t)}>
            {t === "form" ? C.detailsTab : C.tabs[t]}</button>
        ))}
      </div>
      <div className="ic-grid">
        <div className="ic-main">{main}</div>
        <aside className="ic-panel" aria-label={C.tabs[shownPanel]} tabIndex={0} data-panel={view === "form" ? shownPanel : view}>
          {tabs.length > 1 ? (
            <div className="ic-tabs" role="group" aria-label="Show">
              {tabs.map((t) => (
                <button key={t} type="button" aria-pressed={shownPanel === t} onClick={() => setPanel({ step, tab: t })}>{C.tabs[t]}</button>
              ))}
            </div>
          ) : null}
          {panels[view === "form" ? shownPanel : view]}
        </aside>
      </div>
      {/* benchmark 5: the save state sits where the eye is when leaving the step */}
      <div className="ic-bar"><div className="ic-bar__start">{back}
        <span className="nc-save" aria-live="polite" data-state={save}>{SAVE_WORDS[save]}</span></div>{next}</div>
    </div>
  );
}

function LoadingRows() {
  return <div className="lm-state lm-state--loading" role="status" aria-live="polite"><span className="ws-visually-hidden">Loading</span>
    <div className="lm-skel" aria-hidden="true">{[0, 1, 2, 3, 4].map((i) => <span key={i} className="lm-skel__row" />)}</div></div>;
}

export function NewContract() {
  useStartFaces(DOCUMENT_FACES);   // W2-5 r2: this draws a document
  const router = useRouter();
  const params = useSearchParams();
  const draftId = params.get("draft");
  const convert = params.get("convert");
  const keep = convert ? `&convert=${encodeURIComponent(convert)}` : "";
  const named = params.get("step");
  const step = named === "review" ? 4 : named === "deal" ? 3 : 2;
  const [published, setPublished] = useState<PublishedTemplate[] | null>(null);
  const [awaiting, setAwaiting] = useState<TemplateCardData[]>([]);
  const [failure, setFailure] = useState<string | null>(null);

  useEffect(() => {
    api.publishedTemplates().then(setPublished).catch((e) => { setPublished([]); setFailure(describeError(e)); });
    api.templates().then((rows) => setAwaiting(rows.filter((t) => t.awaiting_approval))).catch(toastFailure("Templates waiting for approval could not be loaded"));
  }, []);

  const setStep = useCallback((s: 2 | 3 | 4) => {
    if (draftId) router.push(`/contracts/new?draft=${draftId}&step=${STEP_PARAM[s]}${keep}`);
  }, [draftId, router, keep]);

  async function startDraft(t: PublishedTemplate, client: Counterparty, brand: string | null) {
    const d = await api.createDraft(t.id, client.id, brand);
    // review change 4: a client whose details are on file and checked goes straight to the deal
    const card = await api.draftClientDetails(d.id).catch(() => null);
    router.push(`/contracts/new?draft=${d.id}&step=${card && (!card.applies || card.client_ready) ? "deal" : "client"}${keep}`);
  }

  if (draftId && published) {
    return <Drafting draftId={draftId} step={step} published={published} setStep={setStep} convertFor={convert} />;
  }
  return (
    <div className="lm-page ic">
      <PageHeader wide title="New contract" back={{ href: "/contracts", label: "Contracts" }}
                  meta={<span>Our template, filled in with the client&rsquo;s details.</span>} />
      <IntakeSteps step={1} done={{}} />
      {failure ? <ErrorState title="Our templates could not be loaded" fix={failure} onRetry={() => window.location.reload()} /> : null}
      {draftId ? <LoadingRows /> : <StepOne published={published} awaiting={awaiting} wanted={params.get("template")} onStart={startDraft} convertFor={convert} />}
    </div>
  );
}
