"use client";

/**
 * Legal configuration admin — locked 52.6 (Steps 21, 29), 49.3, rule 16, rule 21.
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

import { AccessRestricted, PermissionGate } from "@/components/AccessRestricted";
import { EmptyState, ErrorBanner, Loading } from "@/components/Feedback";
import { Field } from "@/components/Primitives";
import { api } from "@/lib/api";
import * as P from "@/lib/permissions";
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
  const [publishCodes, setPublishCodes] = useState("");

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
    try {
      const codes = publishCodes
        .split(",")
        .map((value) => value.trim())
        .filter(Boolean);
      setSnapshot(await api.publishConfiguration(codes.length > 0 ? codes : undefined));
      await load();
    } catch (cause) {
      setError(cause);
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
          <button type="submit" className="btn btn--primary">
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
          <form className="form-row" onSubmit={publish}>
            <Field id="publish-codes" label="Requirement codes to activate (comma separated; blank to publish current active configuration only)" grow>
              <input
                id="publish-codes"
                value={publishCodes}
                onChange={(event) => setPublishCodes(event.target.value)}
              />
            </Field>
            <button type="submit" className="btn btn--primary">
              Publish
            </button>
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
        <StandardEditor
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

/**
 * "Edit and save" a Company Standard — which the server implements by APPENDING a
 * new version (locked rule 16). The form is pre-filled with the chosen version's
 * stored values, so restoring an older version is the same operation as changing the
 * current one; there is deliberately no separate rollback control and no in-place
 * edit anywhere on this screen.
 *
 * Values are the organization's own material and are passed through exactly as
 * written (rule 21, ENG-09): nothing here defaults, normalizes or suggests a value.
 * `reason` is required by the API and by the form, because the audit trail records
 * why a legal position changed.
 */
function StandardEditor({
  requirementId,
  version,
  onClose,
  onSaved,
}: {
  requirementId: string;
  version: RequirementVersion;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    const form = new FormData(event.currentTarget);
    try {
      await api.updateCompanyStandard(requirementId, {
        company_standard: JSON.parse(String(form.get("company_standard") || "{}")),
        reason: String(form.get("reason") ?? ""),
      });
      onSaved();
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="card" onSubmit={submit}>
      <h4>Company Standard — from v{version.version_number}</h4>
      <p className="hint">
        Saving appends a new Requirement version carrying the mapping rules,
        evaluation rules and Legal Rule forward unchanged. No existing version is
        modified, so every historical Review stays reproducible, and the change
        affects no Review until it is published into a snapshot. The standard must
        declare a <code>document_type</code>; the server refuses one that does not.
      </p>
      <ErrorBanner error={error} />
      <label>
        Company Standard (JSON)
        <textarea
          name="company_standard"
          rows={10}
          required
          defaultValue={JSON.stringify(version.company_standard ?? {}, null, 2)}
        />
      </label>
      <label>
        Reason for the change (required — recorded in the audit trail)
        <input name="reason" required />
      </label>
      <button type="submit" className="btn btn--primary" disabled={busy}>
        {busy ? "Saving…" : "Save as a new version"}
      </button>{" "}
      <button type="button" className="link" onClick={onClose}>
        Cancel
      </button>
    </form>
  );
}
