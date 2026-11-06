"use client";

/**
 * New contract (S5, flow 1 "Sales creates") — our NDA or MSA for a client from a PUBLISHED
 * template (`AM-282` r4 / `AM-283`), in three steps: what and who, the details beside the
 * live contract, review and create. The answers live on the server as a draft
 * (`AM-295`): every save sends `expected_version`; a 409 means another tab saved first.
 * The created v1 is reviewed by the same engine as any upload — this page decides nothing.
 */

import { PageHeader } from "@/components/page/PageHeader";
import { ACTION } from "@/lib/labels";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api, ApiError, describeError } from "@/lib/api";
import {
  BRANDS, DOC_TYPES, OURS, answered, checkWords, display, groups, outsideRange, problemWords, profileValue,
  toAnswers, unanswered, unavailable,
  type Answers, type Draft, type DraftCheck, type DraftPreview, type FieldProblem, type PublishedTemplate, type Question,
} from "@/lib/newContract";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import { BLANK_NOTE, blankPath, brandLabel, templateName } from "@/lib/templates";
import { DownloadMenu } from "@/components/templates/DownloadMenu";
import type { Counterparty } from "@/lib/types";
import { UploadContractDialog } from "@/components/workspace/UploadContractDialog";
import { requirementTitle } from "@/components/workspace/findingLanguage";

import { ClientPicker } from "./ClientPicker";
import { ContractPreview } from "./ContractPreview";
import { QuestionField, questionId, type ProfileLink } from "./QuestionField";
import "./newcontract.css";

type Step = 1 | 2 | 3;

/** Who each brand is — the Constitution's own entity section (§5: one legal entity,
 *  CloudPe a brand it operates; the brands' services as its table lists them). */
const BRAND_LINES: Record<string, string> = {
  LEAPSWITCH: "Leapswitch Networks Pvt. Ltd., for Bare Metal, Colocation and hosting",
  CLOUDPE: "A brand operated by Leapswitch Networks Pvt. Ltd., for VPS, GPU Cloud and Kubernetes",
};
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

export function Steps({ step }: { step: Step }) {
  const names = ["What and who", "Details", "Review and create"];
  return (
    <ol className="nc-steps" aria-label="Steps">
      {names.map((n, i) => (
        <li key={n} {...(i + 1 === step ? { "aria-current": "step" as const } : {})} data-done={i + 1 < step || undefined}>
          <span className="nc-steps__n">{i + 1}</span>{n}
        </li>
      ))}
    </ol>
  );
}

/** No published template for this type and brand: say why in plain words, and what to do. */
export function NoTemplate({ reason, approver, onUpload }: { reason: string; approver: boolean; onUpload: () => void }) {
  const cloudpe = reason.startsWith("No CloudPe MSA");
  return (
    <div className="nc-blocked" role="status">
      <p className="nc-blocked__why">{reason}</p>
      <p className="nc-quiet">
        {cloudpe ? "Choose LeapSwitch for an MSA, or make a CloudPe NDA."
          : "You can upload a contract instead, or come back once it is published."}
      </p>
      <div className="nc-actions nc-actions--start">
        {!cloudpe ? <button type="button" className="ws-btn" onClick={onUpload}>Upload a contract</button> : null}
        {!cloudpe && approver ? <Link className="nc-link" href="/templates">Open Templates</Link> : null}
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

// ---------------------------------------------------------------- step 1
function StepOne({ published, onStart }: {
  published: PublishedTemplate[] | null;
  onStart: (t: PublishedTemplate, client: Counterparty) => Promise<void>;
}) {
  const { can } = useSession();
  const [docType, setDocType] = useState<string | null>(null);
  const [brand, setBrand] = useState<string | null>(null);
  const [client, setClient] = useState<Counterparty | null>(null);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const brands = BRANDS.filter((b) => !(docType === "MSA" && b === "CLOUDPE"));
  const effectiveBrand = brand && brands.includes(brand as (typeof BRANDS)[number]) ? brand : null;
  const reason = docType && (effectiveBrand || docType === "MSA") && published
    ? unavailable(docType, effectiveBrand ?? "LEAPSWITCH", published) : null;
  const template = docType && effectiveBrand && published
    ? published.find((t) => t.doc_type === docType && t.brand === effectiveBrand) : undefined;

  async function start() {
    if (!template || !client) return;
    setBusy(true); setFailure(null);
    try { await onStart(template, client); } catch (e) { setFailure(describeError(e)); setBusy(false); }
  }

  return (
    <div className="nc-one">
      <fieldset className="nc-pick">
        <legend className="nc-sub">What are you making?</legend>
        <div className="nc-pick__row">
          {DOC_TYPES.map((t) => (
            <label key={t.id} className="nc-option">
              <input type="radio" name="nc-type" checked={docType === t.id} onChange={() => setDocType(t.id)} />
              <span className="nc-item__l1">{t.name}</span>
              <span className="nc-item__l2">{t.long}</span>
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset className="nc-pick">
        <legend className="nc-sub">Which company is it from?</legend>
        <div className="nc-pick__row">
          {brands.map((b) => (
            <label key={b} className="nc-option">
              <input type="radio" name="nc-brand" checked={effectiveBrand === b} onChange={() => setBrand(b)} />
              <span className="nc-item__l1">{brandLabel(b)}</span>
              <span className="nc-item__l2">{BRAND_LINES[b]}</span>
            </label>
          ))}
          {docType === "MSA" ? (
            <p className="nc-option nc-option--none">
              <span className="nc-item__l1">CloudPe</span>
              <span className="nc-item__l2">Not available for an MSA. CloudPe services are governed by the published CloudPe Terms of Service.</span>
            </p>
          ) : null}
        </div>
      </fieldset>

      {template ? (
        <div className="nc-blank">
          <DownloadMenu variant="link" align="start" path={blankPath(template)} label="Download blank copy" />
          <p className="nc-quiet">{BLANK_NOTE}</p>
        </div>
      ) : null}

      {reason && effectiveBrand ? (
        <NoTemplate reason={reason} approver={can(P.LEGAL_APPROVE_CUSTOMIZATION)} onUpload={() => setUploading(true)} />
      ) : null}

      {template ? (
        <section className="nc-pick" aria-labelledby="nc-who">
          <h2 id="nc-who" className="nc-sub">Who is it with?</h2>
          <ClientPicker value={client} onChange={setClient} />
        </section>
      ) : null}

      {published === null ? <p className="nc-quiet">Loading our templates…</p> : null}
      {failure ? <p className="nc-error" role="alert">{failure}</p> : null}
      {template ? (
        <div className="nc-foot">
          <button type="button" className="ws-btn ws-btn--primary" disabled={!client || busy} onClick={() => void start()}>
            {busy ? "Starting…" : "Continue to details"}
          </button>
          {!client ? <p className="nc-quiet">Choose or add the client first.</p> : null}
        </div>
      ) : null}
      {uploading ? <UploadContractDialog firstRun={false} onClose={() => setUploading(false)} /> : null}
    </div>
  );
}

// ---------------------------------------------------------------- steps 2 and 3
/** Our side in one line (`Our company`): the entity our template fixes and who signs.
 *  Change opens the questions; a value our template fixes stays fixed inside. */
function OurCompany({ questions, local, open, onOpen, children }: {
  questions: Question[]; local: Answers; open: boolean; onOpen: (open: boolean) => void; children: React.ReactNode;
}) {
  const by = (role: string) => questions.find((q) => q.role === role || q.key === role);
  const name = by("our_name");
  const signer = by("our_signatory_name");
  const title = by("our_signatory_designation");
  const signs = signer && answered(signer, local[signer.key]) ? String(local[signer.key]) : null;
  const as = title && answered(title, local[title.key]) ? String(local[title.key]) : null;
  const missing = questions.filter((q) => (q.class ?? "M") !== "O" && q.locked_value === undefined && !answered(q, local[q.key]));
  return (
    <section className="nc-group nc-ours" aria-labelledby="nc-g-ours">
      <h2 id="nc-g-ours" className="nc-sub">{OURS}</h2>
      <div className="nc-ours__line">
        <div>
          <p className="nc-item__l1">{name ? display(name, name.locked_value ?? local[name.key]) : "Our company"}</p>
          <p className="nc-item__l2">
            {signs ? `Signed by ${signs}${as ? `, ${as}` : ""}`
              : missing.length ? `${missing[0]!.label} is not chosen yet` : "Fixed by our template"}
          </p>
        </div>
        <button type="button" className="ws-btn ws-btn--sm" aria-expanded={open} aria-controls="nc-ours-fields"
                onClick={() => onOpen(!open)}>{open ? "Done" : signs ? "Change" : "Choose who signs"}</button>
      </div>
      {open ? <div id="nc-ours-fields" className="nc-group">{children}</div> : null}
    </section>
  );
}

/** The early check's answer for one saved version of the draft. */
type Checked = { version: number; check: DraftCheck | null };

function Drafting({ draftId, step, published, setStep }: {
  draftId: string;
  step: 2 | 3;
  published: PublishedTemplate[];
  setStep: (s: Step) => void;
}) {
  const router = useRouter();
  const [draft, setDraft] = useState<Draft | null>(null);
  const [local, setLocal] = useState<Answers>({});
  const [preview, setPreview] = useState<DraftPreview | null>(null);
  const [client, setClient] = useState<Counterparty | null>(null);
  const [save, setSave] = useState<SaveState>("idle");
  const [fresh, setFresh] = useState<string | null>(null);
  const [view, setView] = useState<"details" | "contract">("details");
  const [failure, setFailure] = useState<string | null>(null);
  const [createProblems, setCreateProblems] = useState<FieldProblem[]>([]);
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

  const refreshPreview = useCallback(() => {
    api.draftPreview(draftId).then(setPreview).catch(() => undefined);
  }, [draftId]);

  const apply = useCallback((d: Draft) => {
    version.current = d.version;
    conflict.current = false;
    localRef.current = d.answers;
    setDraft(d); setLocal(d.answers); setSave("idle");
    refreshPreview();
    if (d.counterparty_id) api.counterparty(d.counterparty_id).then(setClient).catch(() => undefined);
    if (d.template_status !== "PUBLISHED") setReplaced(true);
  }, [refreshPreview]);

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
        const r = await saveOnce(draftId, toAnswers(questions, localRef.current), version.current);
        if (r.kind === "saved") {
          version.current = r.draft.version;
          setDraft(r.draft); setSave("saved");
          refreshPreview();
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
  }, [draftId, questions, refreshPreview]);

  function change(key: string, value: unknown) {
    localRef.current = { ...localRef.current, [key]: value };
    setLocal(localRef.current);
    setFresh(key);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => void flush(), 600);
  }

  function jump(key: string) {
    setStep(2);
    setView("details");
    if (questions.find((q) => q.key === key)?.group === OURS) setOursOpen(true);
    requestAnimationFrame(() => requestAnimationFrame(() => {
      const el = document.getElementById(questionId(key));
      if (!el) return;
      el.scrollIntoView({ block: "center", behavior: "smooth" });
      const target = el.matches("fieldset") ? el.querySelector<HTMLElement>("input:checked, input") : el;
      (target ?? el).focus({ preventScroll: true });
    }));
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

  const left = unanswered(questions, local);
  const blocked = save === "conflict";
  // the early check: on the review step, once every required detail is in and saved
  const checkable = step === 3 && !!draft && !left.length && save !== "saving" && !blocked && !creating;
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
    if (timer.current) clearTimeout(timer.current);
    await flush();
    if (conflict.current || !draft) return;
    setCreating(true); setFailure(null); setCreateProblems([]);
    try {
      const made = await api.createFromDraft(draftId, version.current, name.trim() || undefined);
      router.push(`/contracts/${made.contract_id}`);
    } catch (e) {
      setCreating(false);
      if (e instanceof ApiError && e.code === "TEMPLATE_NOT_PUBLISHED") setReplaced(true);
      else if (e instanceof ApiError && e.fieldProblems?.length) setCreateProblems(e.fieldProblems);
      else if (e instanceof ApiError && e.isConflict) { conflict.current = true; setSave("conflict"); }
      else setFailure(describeError(e));
    }
  }

  if (failure && !draft) {
    return <div className="nc-one"><p className="nc-error" role="alert">{failure}</p>
      <Link className="ws-btn" href="/contracts/new">Start a new contract</Link></div>;
  }
  if (!draft) return <div className="nc-one"><p className="nc-quiet">Loading the draft…</p></div>;
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
  const otherProblems = [...createProblems, ...draft.problems.filter((p) => p.problem !== "is required")]
    .filter((p, i, all) => !asked.has(p.field) && all.findIndex((x) => x.field === p.field && x.problem === p.problem) === i);
  const ownProblems = questions.filter((q) => outsideRange(q, local[q.key]));
  const ready = !left.length && !otherProblems.length && !ownProblems.length && !blocked;
  const title = template.title ?? templateName(template);
  const shownGroups = groups(questions, local);
  const fromProfile = questions.filter((q) => {
    const v = profileValue(clientRecord, q);
    return v != null && String(local[q.key] ?? "").trim() === v.trim();
  }).length;

  const forward = step === 2 ? (
    <button type="button" className="ws-btn ws-btn--primary" disabled={blocked}
            onClick={() => { void flush(); setStep(3); setView("details"); }}>Review and create</button>
  ) : (
    <button type="button" className="ws-btn ws-btn--primary" disabled={!ready || creating} onClick={() => void create()}>
      {creating ? "Creating…" : ACTION.createContract}
    </button>
  );

  const head = (
    <PageHeader wide title="New contract" back={{ href: "/contracts", label: "Contracts" }}
      meta={<>
        <span>{templateName(template)}{client ? ` for ${client.name}` : ""}</span>
        <span className="nc-save" aria-live="polite" data-state={save}>{SAVE_WORDS[save]}</span>
      </>}
      primary={forward} />
  );

  const field = (q: Question) => (
    <QuestionField key={q.key} q={q} value={local[q.key]} problem={serverProblem.get(q.key)}
                   profile={profileLink(q)} onChange={change} />
  );

  const form = (
    <div className="nc-form">
      {blocked ? <ConflictBanner onReload={reload} /> : null}
      {fromProfile ? <p className="nc-note">{fromProfile} answer{fromProfile === 1 ? "" : "s"} filled in from {client?.name ?? "the client"}&rsquo;s profile. Check them; a change can be saved back to the profile.</p> : null}
      {shownGroups.map((g) => g.name === OURS ? (
        <OurCompany key={g.name} questions={g.questions} local={local} open={oursOpen} onOpen={setOursOpen}>
          {g.questions.filter((q) => q.role !== "our_name").map(field)}
        </OurCompany>
      ) : (
        <section key={g.name} className="nc-group" aria-labelledby={`nc-g-${g.name}`}>
          <h2 id={`nc-g-${g.name}`} className="nc-sub">{g.name}</h2>
          {g.questions.map(field)}
        </section>
      ))}
    </div>
  );

  const points = check?.check?.points ?? [];
  const review = (
    <div className="nc-form nc-review">
      {blocked ? <ConflictBanner onReload={reload} /> : null}
      <h2 className="nc-sub">Review and create</h2>
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
      ) : <p className="nc-ok">Every required detail is filled in.</p>}

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
            <ul className="nc-check__list">
              {points.map((p) => (
                <li key={p.code}><span className="nc-item__l1">{requirementTitle({ code: p.code, name: p.name })}</span>
                  <span className="nc-item__l2">{checkWords(p.classification)}</span></li>
              ))}
            </ul>
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
        <input id="nc-name" type="text" aria-describedby="nc-name-help" value={name} placeholder={`${title}${client ? `, ${client.name}` : ""}`}
               onChange={(e) => setName(e.target.value)} />
      </div>
      <p className="nc-explain">
        When you create it, our review reads it against our standards, as it does any contract. Anything outside our
        standard goes to Legal before it can be sent.
      </p>
      {failure ? <p className="nc-error" role="alert">{failure}</p> : null}
      {creating ? <p className="nc-quiet" role="status">Creating the contract and starting our review…</p> : null}
      <div className="nc-actions nc-actions--start">
        <button type="button" className="ws-btn" onClick={() => setStep(2)}>Back to details</button>
      </div>
    </div>
  );

  return (
    <div className="nc" data-view={view}>
      {head}
      <Steps step={step} />
      <div className="nc-toggle" role="group" aria-label="Show">
        <button type="button" aria-pressed={view === "details"} onClick={() => setView("details")}>{step === 3 ? "Review" : "Details"}</button>
        <button type="button" aria-pressed={view === "contract"} onClick={() => setView("contract")}>Contract</button>
      </div>
      <div className="nc-grid">
        <div className="nc-left-col">{step === 2 ? form : review}</div>
        <div className="nc-well" aria-label="Live preview">
          <p className="nc-well__note">The wording is fixed by our template. Only your answers change it.</p>
          {preview?.model ? (
            <ContractPreview model={preview.model} questions={questions} local={local} fresh={fresh} onJump={jump} />
          ) : <p className="nc-quiet">{preview ? "The preview could not be drawn yet." : "Drawing the contract…"}</p>}
        </div>
      </div>
      <div className="nc-bar">{forward}</div>
    </div>
  );
}

export function NewContract() {
  const router = useRouter();
  const params = useSearchParams();
  const draftId = params.get("draft");
  const step: Step = !draftId ? 1 : params.get("step") === "review" ? 3 : 2;
  const [published, setPublished] = useState<PublishedTemplate[] | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  useEffect(() => {
    api.publishedTemplates().then(setPublished).catch((e) => { setPublished([]); setFailure(describeError(e)); });
  }, []);

  const setStep = useCallback((s: Step) => {
    if (!draftId) return;
    router.push(s === 3 ? `/contracts/new?draft=${draftId}&step=review` : `/contracts/new?draft=${draftId}`);
  }, [draftId, router]);

  async function startDraft(t: PublishedTemplate, client: Counterparty) {
    const d = await api.createDraft(t.id, client.id);
    router.push(`/contracts/new?draft=${d.id}`);
  }

  if (draftId && published) {
    return <Drafting draftId={draftId} step={step as 2 | 3} published={published} setStep={setStep} />;
  }
  return (
    <div className="lm-page nc-start">
      <PageHeader title="New contract" back={{ href: "/contracts", label: "Contracts" }}
                  meta={<span>Our template, filled in with the client&rsquo;s details.</span>} />
      <div className="nc nc--one">
      <Steps step={1} />
      {failure ? <p className="nc-error" role="alert">{failure}</p> : null}
      {draftId ? <p className="nc-quiet">Loading…</p> : <StepOne published={published} onStart={startDraft} />}
      </div>
    </div>
  );
}
