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
 */

import { useCallback, useEffect, useState } from "react";

import { AccessRestricted, PermissionGate } from "@/components/AccessRestricted";
import { EmptyState, ErrorBanner, Loading } from "@/components/Feedback";
import { api } from "@/lib/api";
import * as P from "@/lib/permissions";
import { useSession } from "@/lib/session";
import type { ConfigurationSnapshot, Requirement } from "@/lib/types";

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
        <form className="card inline" onSubmit={createRequirement}>
          <label>
            New Requirement code
            <input
              required
              value={code}
              onChange={(event) => setCode(event.target.value)}
            />
          </label>
          <button type="submit">Create draft Requirement</button>
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
          <form className="inline" onSubmit={publish}>
            <label>
              Requirement codes to activate (comma separated; blank to publish current
              active configuration only)
              <input
                value={publishCodes}
                onChange={(event) => setPublishCodes(event.target.value)}
              />
            </label>
            <button type="submit">Publish</button>
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
      {requirement.versions.length === 0 ? (
        <p className="hint">No versions yet.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Version</th>
              <th>Name</th>
              <th>Evaluator</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {requirement.versions.map((version) => (
              <tr key={version.id}>
                <td>v{version.version_number}</td>
                <td>{version.name}</td>
                <td>{version.evaluator_type}</td>
                <td>{version.created_at ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

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
              <textarea name="company_standard" rows={4} required defaultValue="{}" />
            </label>
            <label>
              Mapping rules (JSON)
              <textarea name="mapping_rules" rows={4} required defaultValue="{}" />
            </label>
            <label>
              Evaluation rules (JSON)
              <textarea name="evaluation_rules" rows={4} required defaultValue="{}" />
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
              <textarea name="legal_rule_configuration" rows={3} defaultValue="{}" />
            </label>
            <button type="submit">Save draft version</button>
          </form>
        ) : null}
      </PermissionGate>
    </section>
  );
}
