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
import { Field } from "@/components/Primitives";
import { api } from "@/lib/api";
import * as P from "@/lib/permissions";
import { publishPlan } from "@/lib/publishPlan";
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

  if (!can(P.CONFIGURATION_VIEW)) return <AccessRestricted what="legal configuration" />;

  async function createRequirement(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await api.createRequirement(code);
      setCode("");
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
    <>
      <h1>Legal configuration</h1>
      <p className="hint">
        Requirements, Company Standards, Legal Rules, mapping rules and evaluation
        rules are versioned. A new version is appended; existing versions are never
        edited, which is what keeps a historical Review reproducible. Drafts do not
        affect any Review until they are published into a snapshot.
      </p>
      <ErrorBanner error={error} />

      <PermissionGate granted={can(P.CONFIGURATION_DRAFT)}>
        <form className="card form-row" onSubmit={createRequirement}>
          <Field id="new-requirement-code" label="New Requirement code">
            <input
              id="new-requirement-code"
              required
              value={code}
              onChange={(event) => setCode(event.target.value)}
            />
          </Field>
          <button type="submit" className="btn btn--primary btn-icon">
            <Plus size={18} />
            Create draft Requirement
          </button>
        </form>
      </PermissionGate>

      <h2>Requirements</h2>
      {requirements === null ? (
        <Loading what="requirements" />
      ) : requirements.length === 0 ? (
        <EmptyState>
          No Requirements are configured. Which Requirements V1 ships with is an open
          decision, and their content must come from the organization&rsquo;s own legal
          material.
        </EmptyState>
      ) : (
        requirements.map((requirement) => (
          <RequirementCard
            key={requirement.id}
            requirement={requirement}
            onChanged={() => void load()}
          />
        ))
      )}

      <PermissionGate granted={can(P.CONFIGURATION_PUBLISH)}>
        <section className="card">
          <h2>Publish a configuration snapshot</h2>
          <p className="hint">
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
            <section className="form-section">
              <h5>
                Waiting to be activated{plan.drafts.length > 0 ? ` — ${plan.drafts.length}` : ""}
              </h5>
              {plan.drafts.length === 0 ? (
                <p className="hint">
                  Nothing is in draft. Publishing now re-pins the{" "}
                  {plan.active.length} already-active Requirement
                  {plan.active.length === 1 ? "" : "s"} into a fresh snapshot.
                </p>
              ) : (
                <>
                  <p className="hint">
                    Ticking a Requirement activates it (DRAFT &rarr; ACTIVE) and pins it
                    into this snapshot. Leaving everything unticked publishes the
                    active configuration as it stands.
                  </p>
                  <ul className="checks">
                    {plan.drafts.map((requirement) => {
                      const blocked = plan.versionless.some((r) => r.code === requirement.code);
                      return (
                        <li key={requirement.id} className="chip">
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
                          <label htmlFor={`publish-${requirement.code}`} className="chip__text">
                            {requirement.code}
                            {blocked ? (
                              /* Activating this makes it ACTIVE, and the publish then
                                 fails on "no version" — refusing the WHOLE snapshot,
                                 not just this one. */
                              <span className="hint"> — no version yet, so publishing it would be refused</span>
                            ) : null}
                          </label>
                        </li>
                      );
                    })}
                  </ul>
                </>
              )}
            </section>

            <details className="form-section">
              <summary>Already active — {plan.active.length}</summary>
              <p className="hint">
                Every one is pinned into the snapshot whether or not anything above is
                ticked. That is what makes a snapshot the whole configuration rather
                than a diff.
              </p>
              <ul className="checks">
                {plan.active.map((requirement) => (
                  <li key={requirement.id} className="chip">
                    <span className="chip__text">{requirement.code}</span>
                  </li>
                ))}
              </ul>
            </details>

            {plan.retired.length > 0 ? (
              <details className="form-section">
                <summary>Retired — {plan.retired.length}</summary>
                <p className="hint">
                  These cannot be published, and publishing does not bring one back:
                  reversing a retirement is an owner decision that goes through the
                  standard file and the record (<code>AM-65</code>).
                </p>
                <ul className="checks">
                  {plan.retired.map((requirement) => (
                    <li key={requirement.id} className="chip">
                      <span className="chip__text">{requirement.code}</span>
                    </li>
                  ))}
                </ul>
              </details>
            ) : null}

            <section className="form-section">
              {plan.blocked ? <p className="field__error" role="alert">{plan.blocked}</p> : null}
              <button
                type="submit"
                className="btn btn--primary btn-icon"
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
    </>
  );
}

function RequirementCard({
  requirement,
  onChanged,
}: {
  requirement: Requirement;
  onChanged: () => void;
}) {
  const { can } = useSession();
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

  return (
    <section className="card">
      <h3>
        {requirement.code} <span className="status">{requirement.status}</span>
      </h3>
      {versions.length === 0 ? (
        <p className="hint">No versions yet.</p>
      ) : (
        <div className="table-wrap">
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
                  <td>{version.created_at ?? "—"}</td>
                  {showValues ? (
                    <td>
                      <ValueCell version={version} />
                      <PermissionGate granted={can(P.CONFIGURATION_DRAFT)}>
                        {version.company_standard ? (
                          <button
                            type="button"
                            className="link"
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

      {versions.length > 0 ? (
        <button type="button" className="link" onClick={() => void toggleValues()}>
          {showValues ? "Hide stored values" : "Show stored values"}
        </button>
      ) : null}
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
        <button type="button" className="link" onClick={() => setOpen((value) => !value)}>
          {open ? "Cancel" : "Draft a new version"}
        </button>
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
            <button type="submit" className="btn btn--primary">
              Save draft version
            </button>
          </form>
        ) : null}
      </PermissionGate>
    </section>
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
