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
import { Plus, Upload } from "lucide-react";

import { AccessRestricted, PermissionGate } from "@/components/AccessRestricted";
import { StandardForm } from "@/components/configuration/StandardForm";
import { Checkbox } from "@/components/ui/checkbox";
import { EmptyState, ErrorBanner, Loading } from "@/components/Feedback";
import { Field, formatDate } from "@/components/Primitives";
import { api } from "@/lib/api";
import * as P from "@/lib/permissions";
import { ACTIVE, publishPlan } from "@/lib/publishPlan";
import {
  NO_FILTERS, STATUS_LABELS, filterRequirements, isFiltered, latestVersion, statusLabel,
  type RequirementFilters,
} from "@/lib/requirementFilter";
import { useSession } from "@/lib/session";
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
  const [filters, setFilters] = useState<RequirementFilters>(NO_FILTERS);

  const load = useCallback(async () => {
    setError(null);
    try {
      const result = await api.requirements({ page_size: 100 });
      setRequirements(result.items);
    } catch (cause) {
      setError(cause);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const plan = publishPlan(requirements, selected);
  const shown = filterRequirements(requirements, filters);
  const filtering = isFiltered(filters);
  const setFilter = (key: keyof RequirementFilters) => (value: string) =>
    setFilters((current) => ({ ...current, [key]: value }));

  if (!can(P.CONFIGURATION_VIEW)) return <AccessRestricted what="legal configuration" />;

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
    <div className="ws-admin">
      {/*
        The same shell Administration uses — head, filter bar, one table — because
        this screen was the only one still stacking a card per row. At 40 ratified
        standards that is a scroll, not a screen, and a reader who has learned one
        list in this product had to learn a second one here.
      */}
      <header className="ws-admin__head">
        <div>
          {/* The nav has always called this "Standards"; the page called itself
              "Legal configuration", so the one word a reader arrives with did not
              appear on the page they arrived at. */}
          <h1>Standards</h1>
          <p className="ws-pane__note">
            The positions this organization measures every contract against. Each is
            versioned: a change appends a new version and never edits an existing
            one, which is what keeps a historical Review reproducible. Nothing here
            affects a Review until it is published into a snapshot.
          </p>
        </div>
        <PermissionGate granted={can(P.CONFIGURATION_DRAFT)}>
          <button
            type="button"
            className="ws-btn ws-btn--primary ws-btn--icon"
            aria-expanded={createOpen}
            onClick={() => setCreateOpen((open) => !open)}
          >
            <Plus size={16} />
            New standard
          </button>
        </PermissionGate>
      </header>

      <ErrorBanner error={error} />

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
            The code names the position, not the document — it is how fixtures,
            snapshots and explanations refer to it. A new standard starts as a draft:
            it carries no version, affects no Review, and appears in nothing until it
            is given one and published.
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

      <div className="ws-filter-bar">
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
            <option value="NUMERIC_COMPARISON">Numeric comparison</option>
            <option value="PRESENCE">Presence</option>
          </select>
        </label>
      </div>

      <div className="ws-admin__body">
        <div className="ws-admin__main">
          {requirements === null ? (
            <Loading what="standards" />
          ) : shown.length === 0 ? (
            <div className="ws-state">
              <h2>{filtering ? "No standard matches." : "No standards are configured."}</h2>
              <p>
                {filtering
                  ? "Try a broader filter — search matches the code and every version name."
                  : "Which Requirements V1 ships with is an open decision, and their content must come from the organization's own legal material."}
              </p>
            </div>
          ) : (
            <>
              {filtering ? (
                <p className="ws-pane__note" role="status" aria-live="polite">
                  Showing {shown.length} of {requirements.length} standards.
                </p>
              ) : null}
              <div className="ws-docs__table">
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Code</th>
                      <th scope="col">Status</th>
                      <th scope="col">Evaluator</th>
                      <th scope="col">Versions</th>
                      <th scope="col">Latest</th>
                    </tr>
                  </thead>
                  <tbody>
                    {shown.map((requirement) => (
                      <RequirementRow
                        key={requirement.id}
                        requirement={requirement}
                        onChanged={() => void load()}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </div>

      <PermissionGate granted={can(P.CONFIGURATION_PUBLISH)}>
        <section className="ws-intake">
          <h2 className="ws-intake__title">Publish a configuration snapshot</h2>
          <p className="ws-pane__note">
            Publishing activates the named draft Requirements and pins the latest
            version of every active Requirement into an immutable snapshot. If any
            active Requirement is missing its Company Standard, mapping rules or
            evaluation rules, publishing is refused rather than producing a snapshot
            that silently skips it.
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
                  {plan.active.length === 1 ? "" : "s"} into a fresh snapshot.
                </p>
              ) : (
                <>
                  <p className="ws-pane__note">
                    Ticking a Requirement activates it (DRAFT &rarr; ACTIVE) and pins it
                    into this snapshot. Leaving everything unticked publishes the
                    active configuration as it stands.
                  </p>
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
                            {requirement.code}
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
                Every one is pinned into the snapshot whether or not anything above is
                ticked. That is what makes a snapshot the whole configuration rather
                than a diff.
              </p>
              <ul className="ws-checks">
                {plan.active.map((requirement) => (
                  <li key={requirement.id} className="ws-check">
                    <span className="ws-check__label">{requirement.code}</span>
                  </li>
                ))}
              </ul>
            </details>

            {plan.retired.length > 0 ? (
              <details className="ws-formsec">
                <summary>Retired — {plan.retired.length}</summary>
                <p className="ws-pane__note">
                  These cannot be published, and publishing does not bring one back:
                  reversing a retirement is an owner decision that goes through the
                  standard file and the record (<code>AM-65</code>).
                </p>
                <ul className="ws-checks">
                  {plan.retired.map((requirement) => (
                    <li key={requirement.id} className="ws-check">
                      <span className="ws-check__label">{requirement.code}</span>
                    </li>
                  ))}
                </ul>
              </details>
            ) : null}

            <section className="ws-formsec">
              {plan.blocked ? <p className="field__error" role="alert">{plan.blocked}</p> : null}
              <button
                type="submit"
                className="ws-btn ws-btn--primary ws-btn--icon"
                disabled={publishing || plan.blocked !== null}
              >
                <Upload size={18} />
                {publishing ? "Publishing…" : plan.action}
              </button>
            </section>
          </form>
          {snapshot ? (
            <p>
              Snapshot <strong>{snapshot.id}</strong> · {snapshot.requirement_count}{" "}
              Requirement{snapshot.requirement_count === 1 ? "" : "s"} ·{" "}
              {snapshot.reused_existing
                ? "identical to an existing snapshot, which was reused"
                : "newly created"}
              . Use this id when starting a Review.
            </p>
          ) : null}
        </section>
      </PermissionGate>
    </div>
  );
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
    try {
      // Every configuration payload is passed through exactly as the Legal admin
      // wrote it. Nothing is defaulted, normalized or filled in (rule 21, ENG-09).
      const body: Record<string, unknown> = {
        name: String(form.get("name") ?? ""),
        evaluator_type: String(form.get("evaluator_type") ?? ""),
        company_standard: JSON.parse(String(form.get("company_standard") || "{}")),
        mapping_rules: JSON.parse(String(form.get("mapping_rules") || "{}")),
        evaluation_rules: JSON.parse(String(form.get("evaluation_rules") || "{}")),
      };
      const description = String(form.get("description") ?? "");
      if (description) body.description = description;
      const ruleType = String(form.get("legal_rule_type") ?? "");
      if (ruleType) {
        body.legal_rule = {
          rule_type: ruleType,
          configuration: JSON.parse(String(form.get("legal_rule_configuration") || "{}")),
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
          <button
            type="button"
            className="ws-btn ws-btn--link"
            aria-expanded={expanded}
            onClick={() => setExpanded((value) => !value)}
          >
            {requirement.code}
          </button>
        </td>
        <td>
          {/* Same rule as the account roster: ACTIVE is the resting state and gets
              no emphasis — a list where every row shouts is a list nobody scans.
              Draft and Retired both mean "not in force", so both carry it. */}
          <span className={`ws-chip${requirement.status === ACTIVE ? "" : " ws-chip--fill ws-chip--outcome-fill"}`}>
            {statusLabel(requirement.status)}
          </span>
        </td>
        <td>{newest?.evaluator_type ?? "\u2014"}</td>
        <td>{versions.length}</td>
        <td>{newest?.created_at?.slice(0, 10) ?? "\u2014"}</td>
      </tr>

      {!expanded ? null : (
      <tr>
        <td colSpan={5}>
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
                  <td>
                    v{version.version_number}
                    {current && version.id === current.id ? " (current)" : ""}
                  </td>
                  <td>{version.name}</td>
                  <td>{version.evaluator_type}</td>
                  <td>{formatDate(version.created_at)}</td>
                  {showValues ? (
                    <td>
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
          <form onSubmit={submit}>
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
                <option value="NUMERIC_COMPARISON">NUMERIC_COMPARISON</option>
                <option value="PRESENCE">PRESENCE</option>
              </select>
            </label>
            <label>
              Company Standard (JSON) — the organization&rsquo;s own position
              <textarea className="code-input" name="company_standard" rows={4} required defaultValue="{}" />
            </label>
            <label>
              Mapping rules (JSON)
              <textarea className="code-input" name="mapping_rules" rows={4} required defaultValue="{}" />
            </label>
            <label>
              Evaluation rules (JSON)
              <textarea className="code-input" name="evaluation_rules" rows={4} required defaultValue="{}" />
            </label>
            <label>
              Legal Rule type (optional — not every Requirement has one)
              <select name="legal_rule_type" defaultValue="">
                <option value="">None</option>
                <option value="THRESHOLD">THRESHOLD</option>
                <option value="ALLOWED_VALUES">ALLOWED_VALUES</option>
                <option value="PRESENCE">PRESENCE</option>
              </select>
            </label>
            <label>
              Legal Rule configuration (JSON)
              <textarea className="code-input" name="legal_rule_configuration" rows={3} defaultValue="{}" />
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
