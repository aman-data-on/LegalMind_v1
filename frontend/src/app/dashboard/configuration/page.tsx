"use client";

/**
 * Legal configuration admin — locked 52.6 (Steps 21, 29), 49.3, rule 16, rule 21.
 *
 * MOVED HERE 2026-09-04, from `/configuration`. The 2026-09-04 live audit called
 * that route "legacy"; implementing the cleanup proved otherwise. This is the ONLY
 * screen in the product that creates a Requirement, appends a Requirement version,
 * updates a Company Standard, or PUBLISHES the configuration snapshot every analysis
 * pins (AUD-04) — and it had no entry in the new shell's navigation, so the one
 * screen that makes analysis possible was reachable only by typing a URL. It is not
 * legacy; it was orphaned. Adopted into the shell unchanged.
 *
 * Its markup still uses the older `.card` / `.btn` / `.field` vocabulary from
 * `globals.css` (which the root layout loads for every route, so it renders
 * correctly here). Restyling 488 lines to the `ws-*` tokens is a separate, purely
 * cosmetic change and is deliberately not bundled with making the capability
 * reachable.
 *
 * **This screen must never author legal content.** Rule 21: real Company Standards,
 * Legal Rules, thresholds, aliases and keyword groups must be supplied by the
 * organization and never manufactured. So the configuration payloads are entered as
 * JSON by an authorized Legal admin and passed through untouched — there is no
 * template, no example threshold, no default tolerance and no suggested keyword
 * group anywhere in this file. A helpful-looking placeholder here would become the
 * organization's legal position by accident, which is precisely the failure rule 21
 * exists to prevent.
 *
 * Locked rule 16 shapes the flow: draft → publish, versions are appended and never
 * edited, publishing produces an immutable snapshot, and a draft never affects an
 * existing Review.
 *
 * **The read path shows the stored values; the write path appends.** Expanding a
 * Requirement fetches the detail response, which the API gates on
 * `configuration.view` and which carries each version's Company Standard and Legal
 * Rule values. "Edit and save" posts to the standard endpoint, which creates a new
 * version carrying the previous mapping, evaluation and Legal Rule artifacts forward
 * unchanged — so the screen offers no in-place edit, and rollback is the same
 * operation with an older version's values, pre-filled from the version list.
 * A `reason` is mandatory because a standard change is a change of legal position.
 */

import { useCallback, useEffect, useState } from "react";
import { ChevronRight, Plus, Upload } from "lucide-react";

import { AccessRestricted, PermissionGate } from "@/components/AccessRestricted";
import { PageHeader } from "@/components/page/PageHeader";
import { StandardForm } from "@/components/configuration/StandardForm";
import { Checkbox } from "@/components/ui/checkbox";
import { ErrorBanner, ErrorState, Loading, LoadingState } from "@/components/Feedback";
import { Field, formatDate } from "@/components/Primitives";
import { api } from "@/lib/api";
import * as P from "@/lib/permissions";
import { ACTIVE, publishPlan } from "@/lib/publishPlan";
import {
  EVALUATOR_LABELS, NO_FILTERS, SORTS, STATUS_LABELS, evaluatorLabel, filterRequirements,
  isFiltered, latestVersion, sortRequirements, statusLabel,
  type RequirementFilters,
} from "@/lib/requirementFilter";
import { useSession } from "@/lib/session";
import { requirementFamily, requirementTitle } from "@/components/workspace/findingLanguage";
import type {
  ConfigurationSnapshot,
  Requirement,
  RequirementVersion,
} from "@/lib/types";

export default function ConfigurationPage() {
  const { can } = useSession();
  const [requirements, setRequirements] = useState<Requirement[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [code, setCode] = useState("");
  const [snapshot, setSnapshot] = useState<ConfigurationSnapshot | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [publishing, setPublishing] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [publishOpen, setPublishOpen] = useState(false);
  const [sort, setSort] = useState("name");
  const [filters, setFilters] = useState<RequirementFilters>(NO_FILTERS);

  // Only for an account that may see it — no refused request before "Access
  // restricted" (review, 2026-10-14).
  const allowed = can(P.CONFIGURATION_VIEW);
  const load = useCallback(async () => {
    if (!allowed) return;
    setError(null);
    try {
      const result = await api.requirements({ page_size: 100 });
      setRequirements(result.items);
    } catch (cause) {
      setError(cause);
    }
  }, [allowed]);

  useEffect(() => {
    void load();
  }, [load]);

  const plan = publishPlan(requirements, selected);
  const shown = sortRequirements(filterRequirements(requirements, filters), sort, stdName);
  const filtering = isFiltered(filters);
  const setFilter = (key: keyof RequirementFilters) => (value: string) =>
    setFilters((current) => ({ ...current, [key]: value }));

  // The page keeps its h1 when access is refused; AccessRestricted itself stays an h2 note.
  if (!allowed) {
    return (
      <div className="lm-page">
        <PageHeader title="Standards" />
        <AccessRestricted what="legal configuration" />
      </div>
    );
  }

  async function createRequirement(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await api.createRequirement(code);
      setCode("");
      setCreateOpen(false);
      await load();
    } catch (cause) {
      setError(cause);
    }
  }

  async function publish(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setSnapshot(null);
    setPublishing(true);
    try {
      const codes = plan.selectable.filter((code) => selected.includes(code));
      setSnapshot(await api.publishConfiguration(codes.length > 0 ? codes : undefined));
      setSelected([]);
      await load();
    } catch (cause) {
      setError(cause);
    } finally {
      setPublishing(false);
    }
  }

  return (
    <div className="lm-page ws-admin">
      {/*
        The same shell Administration uses — head, filter bar, one table — because
        this screen was the only one still stacking a card per row. At 40 ratified
        standards that is a scroll, not a screen, and a reader who has learned one
        list in this product had to learn a second one here.
      */}
      {/* The house page header. The nav calls this "Standards", so the page does too. */}
      <PageHeader title="Standards"
                  meta={<span>The positions every contract is measured against. A change applies only once it is published.</span>}
                  secondary={(
                    <PermissionGate granted={can(P.CONFIGURATION_PUBLISH)}>
                      <button type="button" className="ws-btn ws-btn--icon" aria-expanded={publishOpen}
                              onClick={() => { setPublishOpen((open) => !open); setCreateOpen(false); }}>
                        <Upload size={16} />
                        Publish a new version
                      </button>
                    </PermissionGate>
                  )}
                  primary={(
                    <PermissionGate granted={can(P.CONFIGURATION_DRAFT)}>
                      <button type="button" className="ws-btn ws-btn--primary ws-btn--icon" aria-expanded={createOpen}
                              onClick={() => { setCreateOpen((open) => !open); setPublishOpen(false); }}>
                        <Plus size={16} />
                        New standard
                      </button>
                    </PermissionGate>
                  )} />

      {requirements !== null ? <ErrorBanner error={error} /> : null}{/* GP-3: a failed list load is said below */}

      {/* The same inline-create shape Administration uses (`ws-intake`), so a
          reader who has added an account already knows this form. */}
      {createOpen ? (
        <form className="ws-intake" onSubmit={createRequirement} aria-labelledby="ws-std-create">
          <h2 id="ws-std-create" className="ws-intake__title">New standard</h2>
          <div className="ws-intake__fields">
            <label className="ws-field">
              <span className="ws-field__label">
                Requirement code <span className="ws-field__req">(required)</span>
              </span>
              <input
                id="new-requirement-code"
                required
                autoFocus
                value={code}
                onChange={(event) => setCode(event.target.value)}
              />
            </label>
          </div>
          <p className="ws-field__help">
            A new standard starts as a draft and affects no review until it is published.
          </p>
          <div className="ws-detail__acts">
            <button type="button" className="ws-btn" onClick={() => setCreateOpen(false)}>
              Cancel
            </button>
            <button type="submit" className="ws-btn ws-btn--primary" disabled={!code.trim()}>
              Create draft
            </button>
          </div>
        </form>
      ) : null}

      {publishOpen ? (
        <PermissionGate granted={can(P.CONFIGURATION_PUBLISH)}>
          <section className="ws-intake">
            <h2 className="ws-intake__title">Publish a new version of our standards</h2>
            <p className="ws-pane__note">
              Publishing saves every active Requirement into a new version that never changes. It is refused if one is missing its Company Standard, mapping rules or evaluation rules.
            </p>
            {/*
              A checkbox list, not a comma-separated field. Activating the AB-20 batch
              meant pasting 33 codes into a text input with nothing on screen saying
              which Requirements were waiting, which were already active, or which
              would be refused — and one typo produced `unknown Requirement code` after
              the fact. Every Requirement with its status is already loaded here, so
              this is a group-by (`lib/publishPlan.ts`), not a new endpoint.
            */}
            <form onSubmit={publish}>
              <section className="ws-formsec">
                <h5>
                  Waiting to be activated{plan.drafts.length > 0 ? ` — ${plan.drafts.length}` : ""}
                </h5>
                {plan.drafts.length === 0 ? (
                  <p className="ws-pane__note">
                    Nothing is in draft. Publishing now re-pins the{" "}
                    {plan.active.length} already-active Requirement
                    {plan.active.length === 1 ? "" : "s"} into a new version.
                  </p>
                ) : (
                  <>
                    <p className="ws-pane__note">
                      Ticked Requirements become active in this version. Leave all unticked to republish the active set.
                    </p>
                    {/* SELECT ALL — 39 individual ticks is the tedium the bulk-action
                        guideline names, and the owner hit it publishing AB-25. Buttons,
                        not a tri-state header checkbox: a header checkbox has to invent
                        an indeterminate state and answer "what does unticking it do to
                        the ones I chose by hand", and two plain verbs answer neither.
                        `selectable` excludes the versionless ones, so Select all can
                        never tick something that would refuse the whole snapshot. */}
                    <div className="ws-checks__bulk">
                      <button
                        type="button"
                        className="ws-btn ws-btn--link"
                        disabled={publishing || selected.length === plan.selectable.length}
                        onClick={() => setSelected(plan.selectable)}
                      >
                        Select all {plan.selectable.length}
                      </button>
                      <button
                        type="button"
                        className="ws-btn ws-btn--link"
                        disabled={publishing || selected.length === 0}
                        onClick={() => setSelected([])}
                      >
                        Clear
                      </button>
                      {/* Polite, not assertive: the count changes on every tick, and an
                          assertive region would interrupt the screen reader each time. */}
                      <span className="ws-pane__note" aria-live="polite">
                        {selected.length} of {plan.selectable.length} selected
                      </span>
                    </div>
                    <ul className="ws-checks">
                      {plan.drafts.map((requirement) => {
                        const blocked = plan.versionless.some((r) => r.code === requirement.code);
                        return (
                          <li key={requirement.id} className="ws-check">
                            <Checkbox
                              id={`publish-${requirement.code}`}
                              checked={selected.includes(requirement.code)}
                              disabled={blocked || publishing}
                              onCheckedChange={(checked) =>
                                setSelected((current) =>
                                  checked === true
                                    ? [...current, requirement.code]
                                    : current.filter((c) => c !== requirement.code),
                                )
                              }
                            />
                            <label htmlFor={`publish-${requirement.code}`} className="ws-check__label">
                              {stdName(requirement)}{" "}
                              <span className="ws-pane__note">{requirement.code}</span>
                              {blocked ? (
                                /* Activating this makes it ACTIVE, and the publish then
                                   fails on "no version" — refusing the WHOLE snapshot,
                                   not just this one. */
                                <span className="ws-pane__note"> — no version yet, so publishing it would be refused</span>
                              ) : null}
                            </label>
                          </li>
                        );
                      })}
                    </ul>
                  </>
                )}
              </section>

              <details className="ws-formsec">
                <summary>Already active — {plan.active.length}</summary>
                <p className="ws-pane__note">
                  All of these are in every new version.
                </p>
                <ul className="ws-checks">
                  {plan.active.map((requirement) => (
                    <li key={requirement.id} className="ws-check">
                      <span className="ws-check__label">{stdName(requirement)}</span>
                    </li>
                  ))}
                </ul>
              </details>

              {plan.retired.length > 0 ? (
                <details className="ws-formsec">
                  <summary>Retired — {plan.retired.length}</summary>
                  <p className="ws-pane__note">
                    These cannot be published or brought back from here.
                  </p>
                  <ul className="ws-checks">
                    {plan.retired.map((requirement) => (
                      <li key={requirement.id} className="ws-check">
                        <span className="ws-check__label">{stdName(requirement)}</span>
                      </li>
                    ))}
                  </ul>
                </details>
              ) : null}

              {/* The actions are not a section: a separator rule with only a button under
                  it draws a line around nothing. */}
              <div className="ws-publish__acts">
                {plan.blocked ? <p className="ws-field__error" role="alert">{plan.blocked}</p> : null}
                <button
                  type="submit"
                  className="ws-btn ws-btn--primary ws-btn--icon"
                  disabled={publishing || plan.blocked !== null}
                >
                  <Upload size={18} />
                  {publishing ? "Publishing…" : plan.action}
                </button>
              </div>
            </form>
            {snapshot ? (
              <p className="ws-stated">
                Version <strong className="ws-stated__value">{snapshot.id}</strong> holds{" "}
                {snapshot.requirement_count} standard{snapshot.requirement_count === 1 ? "" : "s"} and is{" "}
                {snapshot.reused_existing
                  ? "identical to an existing version, which was reused"
                  : "newly created"}
                . Use this id when starting a Review.
              </p>
            ) : null}
          </section>
        </PermissionGate>
      ) : null}
      {requirements === null ? null : <div className="ws-filter-bar">{/* GP-3: filters wait for the list */}
        <label className="ws-field">
          <span className="ws-field__label">Search</span>
          <input
            type="search"
            aria-label="Search standards"
            placeholder="Code or name"
            value={filters.search}
            onChange={(event) => setFilter("search")(event.target.value)}
          />
        </label>
        <label className="ws-field">
          <span className="ws-field__label">Status</span>
          <select
            aria-label="Filter standards by status"
            value={filters.status}
            onChange={(event) => setFilter("status")(event.target.value)}
          >
            <option value="">Any status</option>
            {STATUS_LABELS.map((option) => (
              <option key={option.code} value={option.code}>{option.label}</option>
            ))}
          </select>
        </label>
        <label className="ws-field">
          <span className="ws-field__label">Evaluator</span>
          <select
            aria-label="Filter standards by evaluator"
            value={filters.evaluator}
            onChange={(event) => setFilter("evaluator")(event.target.value)}
          >
            {/*
              Exactly the two locked evaluator types (AM-16), as a filter. A third
              option here would be inventing an evaluator just as surely as one in
              the create form would.
            */}
            <option value="">Any evaluator</option>
            {EVALUATOR_LABELS.map((option) => (
              <option key={option.code} value={option.code}>{option.label}</option>
            ))}
          </select>
        </label>
        <label className="ws-field">
          <span className="ws-field__label">Sort by</span>
          <select
            aria-label="Sort standards by"
            value={sort}
            onChange={(event) => setSort(event.target.value)}
          >
            {SORTS.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
      </div>}

      <div className="ws-admin__body">
        <div className="ws-admin__main">
          {requirements === null && error ? <ErrorState title="Standards could not be loaded" error={error} onRetry={() => void load()} />
          : requirements === null ? <LoadingState label="Loading standards…" rows={6} />
          : shown.length === 0 ? (
            <div className="ws-state">
              <h2>{filtering ? "No standard matches." : "No standards are configured."}</h2>
              <p>
                {filtering
                  ? "Try a broader filter — search matches the code and every version name."
                  : "Standards appear here once Legal adds them."}
              </p>
            </div>
          ) : (
            <>
              <p className="ws-pane__note ws-std__count" role="status" aria-live="polite">
                {filtering
                  ? `Showing ${shown.length} of ${requirements.length} standards.`
                  : `${requirements.length} standard${requirements.length === 1 ? "" : "s"}.`}
              </p>
              {/* B3 p4: grouped by contract family, each a disclosure — the first open; a
                  search or filter opens them all */}
              {groupStandards(shown).map(([family, rows], index) => (
                <details key={family} className="ws-stdgroup" open={filtering || index === 0}>
                  <summary>{family} <span className="ws-pane__note">{rows.length}</span></summary>
                  <div className="ws-docs__table ws-stdtable">
                    <table>
                      <thead>
                        <tr>
                          <th scope="col">Standard</th>
                          <th scope="col">Status</th>
                          <th scope="col">Evaluator</th>
                          <th scope="col">Latest version</th>
                        </tr>
                      </thead>
                      <tbody>
                        {rows.map((requirement) => (
                          <RequirementRow key={requirement.id} requirement={requirement}
                                          onChanged={() => void load()} />
                        ))}
                      </tbody>
                    </table>
                  </div>
                </details>
              ))}
            </>
          )}
        </div>
      </div>

    </div>
  );
}

/** B3 p4: a standard's plain name — the server's own version name, else words from its code.
 *  The stored code is untouched; it shows only in the expanded row. */
function stdName(requirement: Requirement): string {
  const name = latestVersion(requirement)?.name?.trim();
  // a name that is itself a code ("ACCEPTANCE-ORDER_FORM-001") is no name to a reader
  return name && !/^[A-Z0-9_-]+$/.test(name) ? name : requirementTitle({ code: requirement.code });
}

/** Standards by the contract family their code declares (MSA, NDA…), in the list's order. */
function groupStandards(rows: Requirement[]): [string, Requirement[]][] {
  const groups = new Map<string, Requirement[]>();
  for (const r of rows) {
    // the declared family (MSA, NDA…), else the contract-type word before the number ("Order form")
    const parts = r.code.split("-");
    const raw = requirementFamily({ code: r.code })
      ?? (parts.length > 2 ? parts[parts.length - 2]! : null);
    const family = raw && raw.length > 3 ? raw.replace(/_/g, " ").toLowerCase().replace(/^./, (c) => c.toUpperCase()) : raw;
    const key = family ? `${family} standards` : "Other standards";
    groups.set(key, [...(groups.get(key) ?? []), r]);
  }
  return [...groups.entries()];
}

function RequirementRow({
  requirement,
  onChanged,
}: {
  requirement: Requirement;
  onChanged: () => void;
}) {
  const { can } = useSession();
  const [expanded, setExpanded] = useState(false);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<unknown>(null);
  // The detail response (values) is fetched on demand: the list response carries
  // none, and loading N detail responses to render a list would defeat that.
  const [detail, setDetail] = useState<Requirement | null>(null);
  const [detailError, setDetailError] = useState<unknown>(null);
  const [showValues, setShowValues] = useState(false);
  const [editing, setEditing] = useState<RequirementVersion | null>(null);

  const loadDetail = useCallback(async () => {
    setDetailError(null);
    try {
      setDetail(await api.requirement(requirement.id));
    } catch (cause) {
      setDetailError(cause);
    }
  }, [requirement.id]);

  async function toggleValues() {
    const next = !showValues;
    setShowValues(next);
    if (next && detail === null) await loadDetail();
  }

  const versions = detail?.versions ?? requirement.versions;
  const current = versions.length > 0 ? versions[versions.length - 1] : null;

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    const form = new FormData(event.currentTarget);
    // QA-064: which field is not valid JSON, and where — named, not a generic failure
    const json = (field: string, label: string): unknown => {
      try {
        return JSON.parse(String(form.get(field) || "{}"));
      } catch (cause) {
        const err = new Error(`${label} is not valid JSON: ${(cause as Error).message}`);
        err.name = "InputError";
        throw err;
      }
    };
    try {
      // Every configuration payload is passed through exactly as the Legal admin
      // wrote it. Nothing is defaulted, normalized or filled in (rule 21, ENG-09).
      const body: Record<string, unknown> = {
        name: String(form.get("name") ?? ""),
        evaluator_type: String(form.get("evaluator_type") ?? ""),
        company_standard: json("company_standard", "Company standard"),
        mapping_rules: json("mapping_rules", "Mapping rules"),
        evaluation_rules: json("evaluation_rules", "Evaluation rules"),
      };
      const description = String(form.get("description") ?? "");
      if (description) body.description = description;
      const ruleType = String(form.get("legal_rule_type") ?? "");
      if (ruleType) {
        body.legal_rule = {
          rule_type: ruleType,
          configuration: json("legal_rule_configuration", "Legal rule configuration"),
        };
      }
      await api.createRequirementVersion(requirement.id, body);
      setOpen(false);
      onChanged();
    } catch (cause) {
      setError(cause);
    }
  }

  const newest = latestVersion(requirement);

  return (
    <>
      {/* One row per standard, expanding in place. A side panel was the other
          option and is wrong here: a standard's detail is its version history and
          a fourteen-field form, which needs the width of the page, not a column. */}
      <tr>
        <td>
          {/* `ws-link`, not `ws-btn--link`: a button inside a table cell brings the
              button's 38px min-height with it, which made every row 62px against
              Administration's 44.5px. Measured, not eyeballed. */}
          <button
            type="button"
            className="ws-link ws-std__name"
            aria-expanded={expanded}
            onClick={() => setExpanded((value) => !value)}
          >
            <ChevronRight size={13} className="ws-std__twist" aria-hidden="true" />
            {stdName(requirement)}
          </button>
        </td>
        <td>
          {/* Same rule as the account roster: ACTIVE is the resting state and gets
              no emphasis — a list where every row shouts is a list nobody scans.
              Draft and Retired both mean "not in force", so both carry it. */}
          <span className={`ws-chip${requirement.status === ACTIVE ? "" : " lm-lozenge"}`}>
            {statusLabel(requirement.status)}
          </span>
        </td>
        <td>{evaluatorLabel(newest?.evaluator_type)}</td>
        <td>
          {newest
            ? `v${newest.version_number}, ${formatDate(newest.created_at)}`
            : "No version yet"}
        </td>
      </tr>

      {!expanded ? null : (
      <tr className="ws-std__detail">
        <td colSpan={4}>
      <p className="ws-pane__note">Code: {requirement.code}</p>
      {versions.length === 0 ? (
        <p className="ws-pane__note">No versions yet.</p>
      ) : (
        <div className="ws-docs__table">
          <table>
            <thead>
              <tr>
                <th>Version</th>
                <th>Name</th>
                <th>Evaluator</th>
                <th>Created</th>
                {showValues ? <th>Company Standard</th> : null}
              </tr>
            </thead>
            <tbody>
              {versions.map((version) => (
                <tr key={version.id}>
                  <td data-label="Version">
                    v{version.version_number}
                    {current && version.id === current.id ? " (current)" : ""}
                  </td>
                  <td data-label="Name">{version.name}</td>
                  <td data-label="Evaluator">{evaluatorLabel(version.evaluator_type)}</td>
                  <td data-label="Created">{formatDate(version.created_at)}</td>
                  {showValues ? (
                    <td data-label="Stored values">
                      <ValueCell version={version} />
                      <PermissionGate granted={can(P.CONFIGURATION_DRAFT)}>
                        {version.company_standard ? (
                          <button
                            type="button"
                            className="ws-btn ws-btn--link"
                            onClick={() => setEditing(version)}
                          >
                            {current && version.id === current.id
                              ? "Change these values"
                              : "Restore these values"}
                          </button>
                        ) : null}
                      </PermissionGate>
                    </td>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* One row, one gap. These two rendered as "Show stored valuesDraft a new
          version" — adjacent JSX siblings whose separating newline is stripped at
          compile time, with nothing between them in the common case. */}
      <div className="ws-detail__acts">
        {versions.length > 0 ? (
          <button type="button" className="ws-btn ws-btn--link" onClick={() => void toggleValues()}>
            {showValues ? "Hide stored values" : "Show stored values"}
          </button>
        ) : null}
        <PermissionGate granted={can(P.CONFIGURATION_DRAFT)}>
          <button type="button" className="ws-btn ws-btn--link" onClick={() => setOpen((value) => !value)}>
            {open ? "Cancel new version" : "Draft a new version"}
          </button>
        </PermissionGate>
      </div>
      <ErrorBanner error={detailError} />
      {showValues && detail === null && detailError === null ? (
        <Loading what="stored configuration" />
      ) : null}

      {editing ? (
        <StandardForm
          requirementId={requirement.id}
          version={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            void loadDetail();
            onChanged();
          }}
        />
      ) : null}

      <PermissionGate granted={can(P.CONFIGURATION_DRAFT)}>
        {open ? (
          <form className="ws-stackform" onSubmit={submit}>
            <ErrorBanner error={error} />
            <label>
              Name
              <input name="name" required />
            </label>
            <label>
              Description (optional)
              <textarea name="description" rows={2} />
            </label>
            <label>
              Evaluator type
              <select name="evaluator_type" required defaultValue="">
                <option value="" disabled>
                  Select
                </option>
                {/*
                  Exactly the two locked evaluator types (AM-16). A third option here
                  would be inventing an evaluator.
                */}
                <option value="NUMERIC_COMPARISON">{evaluatorLabel("NUMERIC_COMPARISON")}</option>
                <option value="PRESENCE">{evaluatorLabel("PRESENCE")}</option>
              </select>
            </label>
            <label>
              Company standard values (JSON; leave empty for none)
              <textarea className="code-input" name="company_standard" rows={4} />
            </label>
            <label>
              How the clause is found (JSON; leave empty for none)
              <textarea className="code-input" name="mapping_rules" rows={4} />
            </label>
            <label>
              How it is compared (JSON; leave empty for none)
              <textarea className="code-input" name="evaluation_rules" rows={4} />
            </label>
            <label>
              Legal Rule type (optional — not every Requirement has one)
              <select name="legal_rule_type" defaultValue="">
                <option value="">None</option>
                {/* plain words; the value sent is the code, unchanged */}
                <option value="THRESHOLD">Minimum or maximum</option>
                <option value="ALLOWED_VALUES">One of a fixed list</option>
                <option value="PRESENCE">Must be present</option>
              </select>
            </label>
            <label>
              Legal Rule settings (JSON — a fixed list stays a JSON list; empty for none)
              <textarea className="code-input" name="legal_rule_configuration" rows={3} />
            </label>
            <button type="submit" className="ws-btn ws-btn--primary">
              Save draft version
            </button>
          </form>
        ) : null}
      </PermissionGate>
        </td>
      </tr>
      )}
    </>
  );
}

/**
 * One version's stored configuration values.
 *
 * The Legal Rule is the confidential Internal Legal Position (LEGAL-02). When the
 * response omits it there is **no marker of any kind** — no dash, no "hidden", no
 * empty row (locked 52.4). The absence is indistinguishable from a Requirement that
 * genuinely has no Legal Rule, which is the point: Step 20 r4 makes it optional, so
 * both cases legitimately render as nothing.
 */
export function ValueCell({ version }: { version: RequirementVersion }) {
  return (
    <>
      {version.company_standard ? (
        <pre>{JSON.stringify(version.company_standard, null, 2)}</pre>
      ) : null}
      {version.legal_rule ? (
        <pre>
          {version.legal_rule.rule_type}{" "}
          {JSON.stringify(version.legal_rule.configuration, null, 2)}
        </pre>
      ) : null}
    </>
  );
}

/*
 * The Company Standard editor moved to `components/configuration/StandardForm.tsx`
 * on 2026-09-15: it is a form now, not a JSON textarea, and at ~450 lines it is its
 * own component rather than a third of this file. The rules it enforces are
 * unchanged — saving APPENDS a version (rule 16), a `reason` is mandatory because a
 * standard change is a change of legal position, and nothing defaults or suggests a
 * value (rule 21).
 */
