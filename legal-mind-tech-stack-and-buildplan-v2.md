# Legal Mind — MSA/TOS/SLA Validation System
## v3: Open-Source Stack + Gemini Flash (LLM only) — Ubuntu 24.04 + Phased Build Plan

**Design constraint: everything self-hosted and open-source EXCEPT the LLM, which is Gemini Flash (hosted API). Every other layer — storage, DB, vector search, parsing, backend, frontend, auth, secrets, security tooling — runs on your own Ubuntu 24.04 infra with no third-party dependency.**

**Direct consequence of this one exception:** document text (or at minimum the retrieved clause-level context) leaves your infra on every LLM call. This is the single point where confidentiality depends on Google's Gemini API terms, not on your own infra. Two things are mandatory before any real customer MSA touches this system:
1. **Confirm Gemini API enterprise data-retention/zero-training terms in writing** — do not rely on default consumer API terms.
2. **Minimize what's sent** — send only the matched clause + minimal surrounding context per call, never the full document, so exposure per call is as small as possible even though it's still leaving the building.

Everything else below stays fully open-source and on-prem, same as before.

---

## 1. What changed from the fully-self-hosted version

Only the LLM layer changed — Llama/Mistral self-hosted inference is replaced with Gemini Flash API calls. Object storage, Postgres, vector DB, parsing, backend, frontend, auth, secrets, and security tooling are unchanged and remain fully open-source and self-hosted.

## 1a. This is a three-domain RAG architecture — stated explicitly
LegalMind's core mechanism is **Retrieval-Augmented Generation (RAG)** across three separate indexes, never a single blended index and never an LLM answering from its own training knowledge:

| Domain | Index | Answers |
|---|---|---|
| **A. Internal Legal Constitution** | pgvector + Postgres FTS, seeded from Leapswitch/CloudPe's approved legal positions (category structure derived from source doc, not hardcoded — see Phase 1) | "Does this clause match our approved position?" |
| **B. Uploaded Document** | pgvector + Postgres FTS, built per-session at upload time | "What does this document say about X?" |
| **C. Statute Corpus** | pgvector + Postgres FTS, pre-indexed at build time from India Code (official government source), prioritized subset for v1 (Contract Act, IT Act, DPDP Act, Companies Act, +Evidence Act/NI Act if time permits) | "What does Section 138 NI Act say?" (general legal research, no uploaded doc) |

Every query — validation, document chat, or general research — retrieves from the relevant domain(s) first, and the LLM only ever synthesizes from what was retrieved. No retrieval match → no LLM call → "Information not found," not a guess.

**Hybrid retrieval** = semantic (pgvector cosine similarity) + keyword (Postgres native full-text search, `tsvector`/`tsquery` — no separate Elasticsearch/OpenSearch service, keeps the stack minimal) combined, so exact statutory section numbers, case numbers, and party names are never missed by vector search alone.

**Chunking differs by domain** — clause/sub-clause boundaries for A and B, Section-number boundaries for C statutes (never split a Section across chunks), paragraph/logical-section boundaries for C judgments.

---

## 2. Finalized Open-Source Stack

| Layer | Choice | Why |
|---|---|---|
| LLM (extraction + judgment) | **Gemini Flash (latest, e.g. 3.7)** — hosted API, the one non-open-source, non-self-hosted component | Only exception to the open-source constraint, by explicit decision. Confirm zero-data-retention/enterprise terms before go-live — hard gate. |
| Inference access | Outbound HTTPS call from `backend-api` only — no other service has network access to call it | Keeps the one external dependency isolated to a single, auditable egress point |
| Structured DB | **PostgreSQL** (self-hosted, own instance) | Rules, clause registry, tenants, audit log |
| Vector DB | **pgvector** extension on the same Postgres, OR **Qdrant** (self-hosted, own container/VM) if scale demands separation | Both fully open-source, self-hostable |
| Document parsing | **unstructured.io (open-source library, not their hosted API)** or **docling** | Runs locally, no calls to unstructured's hosted endpoint — pin to the OSS pip package explicitly |
| Backend | **FastAPI** | Open-source, self-hosted |
| Frontend | **Next.js** | Open-source, self-hosted, served from your own Nginx |
| Object storage | **MinIO** (self-hosted, S3-compatible API) | Replaces AWS S3 — same API, runs entirely on your infra |
| Reverse proxy / TLS | **Nginx** + **Certbot** (Let's Encrypt) or internal CA if fully air-gapped | Open-source |
| Auth | Existing RIAAS layer | Already internal |
| Secrets management | **HashiCorp Vault (OSS edition)** or `.env` + OS-level encrypted disk (LUKS) if Vault is overkill for V1 | No secrets in code or config files, ever |
| Guardrails | Custom Python module, no external calls | Citation verification, confidence threshold, cross-ref hard-gate |
| Audit logging | PostgreSQL `audit_log` table + **Wazuh** or **auditd** at OS level | Immutable trail, tamper-evident |
| Firewall | **ufw** (Ubuntu default) or **nftables** | Segment every service, deny-by-default |
| Container isolation | **Docker** + **Docker Compose**, each service in its own container, own network namespace | Enables clean folder-per-stack structure and network segmentation |
| Intrusion / pen-test readiness | **OpenVAS** or **Trivy** (container scanning) + **OWASP ZAP** for the web layer, run pre-deployment and on a schedule | All open-source |

**Hardware note:** Llama 3.1 70B / Mistral Large needs real GPU (2x A100/H100-class or equivalent, or quantized to run on smaller GPUs at some accuracy cost). If Leapswitch/CloudPe has GPU infra internally (which, given CloudPe's positioning, you likely do), this is where it runs. Confirm GPU allocation before Phase 1 — this is the one dependency that can block the whole timeline if not pre-provisioned.

---

## 3. Folder / Service Structure (per-component isolation)

Each stack component gets its own directory, own Docker container, own internal network segment, own service account — no shared credentials, no shared filesystem access between components.

```
/opt/legal-mind/
├── infra/
│   ├── docker-compose.yml          # orchestrates all services, isolated networks per tier
│   ├── nginx/                      # reverse proxy configs, TLS certs
│   ├── ufw-rules/                  # firewall rule sets, versioned
│   └── vault/                      # secrets engine config (or encrypted .env vault)
│
├── db-postgres/
│   ├── schema/                     # migrations, versioned SQL
│   ├── init/                       # seed data (8 clause categories, 22-conflict register)
│   └── backup/                     # automated backup scripts, encrypted dumps
│
├── db-vector/                      # pgvector config OR standalone Qdrant service
│   └── config/
│
├── storage-minio/
│   ├── config/
│   └── buckets/                    # bucket policy definitions, per-tenant bucket isolation
│
├── llm-gateway/
│   ├── client/                     # single wrapped interface: validate_clause(clause, context) → verdict
│   ├── redaction/                  # strips PII/party names before sending context out, where policy allows
│   └── egress-policy/              # allow-list: only Gemini API endpoint, only from this service
│
├── backend-api/
│   ├── app/
│   │   ├── ingestion/              # upload, parsing, clause extraction
│   │   ├── retrieval/              # rules lookup + vector search
│   │   ├── guardrails/             # citation verification, confidence gate, cross-ref gate — own module, own tests
│   │   ├── validation/             # LLM call orchestration behind single interface
│   │   └── audit/                  # logging, immutable trail writer
│   └── tests/
│
├── frontend-web/
│   ├── app/                        # Next.js app
│   └── public/
│
├── auth/
│   └── riaas-integration/          # existing auth layer, isolated config
│
├── security/
│   ├── scans/                      # OpenVAS/Trivy/ZAP scan configs + scheduled run scripts
│   ├── audit-logs/                 # auditd/Wazuh config, tamper-evident storage
│   └── pentest-reports/            # dated reports, version-controlled, access-restricted
│
└── docs/
    └── runbooks/                   # deployment, rollback, incident response
```

**Isolation rules enforced at the infra level:**
- Each container runs as its own non-root user, own service account, own Docker network — `db-postgres` cannot reach `frontend-web` directly; all cross-service traffic routes through `backend-api` only.
- `llm-gateway` is the **only** container with outbound internet access, and its egress is allow-listed to the Gemini API endpoint alone — no other domain, no other service in the stack can reach the internet at all.
- `db-postgres`, `db-vector`, `storage-minio` have zero outbound internet access — verified, not assumed.
- `storage-minio` buckets are per-tenant, access-scoped via RIAAS-issued tokens, never a shared bucket across customers.
- Secrets never live in `docker-compose.yml` or any committed file — pulled from Vault or an encrypted `.env` mounted at runtime only. Gemini API key included — never hardcoded, never logged.
- `security/pentest-reports` and `security/audit-logs` are read-restricted even from most engineers — audit trail must survive a compromised app-layer account.
- Every outbound call from `llm-gateway` is logged to `audit_log` with clause ID, timestamp, and payload hash (not full payload) — gives you a record of exactly what left the building and when, without duplicating sensitive content in logs.

---

## 4. Security & Pen-Test-Readiness Checklist

| Control | Implementation |
|---|---|
| Network segmentation | Docker networks per tier (frontend / backend / db / llm-gateway / storage), `ufw` deny-by-default, only required ports open between segments |
| No internet egress from data-handling services | `db-postgres`, `db-vector`, `storage-minio` containers have zero outbound internet route — verify with `iptables`/`ufw` rule audit. `llm-gateway` is the sole exception, allow-listed to the Gemini API endpoint only |
| Minimize external exposure per call | `llm-gateway` sends only the matched clause + minimal context, never the full document; redact party names/PII where policy allows before the call |
| Vendor data-handling terms confirmed | Gemini API enterprise zero-retention/no-training terms confirmed in writing before any live customer document is processed — hard go/no-go gate |
| Encryption at rest | LUKS full-disk encryption on the host, plus Postgres/MinIO native encryption-at-rest config |
| Encryption in transit | TLS everywhere internally too, not just the public-facing edge — service-to-service calls over TLS via Nginx internal proxying or mutual TLS between containers |
| Secrets management | Vault (or encrypted `.env` + LUKS) — zero secrets in git, zero secrets in logs |
| Least privilege | Per-service DB roles (extraction service can't write to `rules` table; only an admin role can) |
| Audit trail integrity | Append-only `audit_log` table + OS-level `auditd`/Wazuh, write access restricted, no delete permission granted to any application-layer role |
| Input validation | All upload/API input validated and sanitized at the FastAPI layer before touching parsing or DB — reject malformed docs early |
| Dependency scanning | `Trivy` scans every container image pre-deploy; `pip-audit`/`npm audit` in CI before merge |
| Pen-test cadence | `OpenVAS` full scan + `OWASP ZAP` web-layer scan before go-live, then scheduled monthly — reports stored in `security/pentest-reports`, dated and version-controlled |
| Access control | RIAAS-issued, role-scoped tokens (reviewer / analyst / admin) — no shared credentials, no static API keys for internal services beyond what Vault issues |
| No unplanned third-party calls anywhere in the request path | Confirm via network egress monitoring in staging — the **only** expected external call is `llm-gateway` → Gemini API; anything else phoning home is a stack violation, fix before go-live |

---

## 5. Ubuntu 24.04 Setup — Start to End, No External Dependency Once Provisioned

1. **Base OS hardening**: Ubuntu 24.04 LTS, `ufw` enabled deny-by-default, `auditd` installed, unattended-security-upgrades on, non-root service accounts for every component.
2. **Docker + Docker Compose**: install from Ubuntu's official repo/Docker's OSS repo (one-time internet access for package install — after this, no runtime internet dependency needed).
3. **Pull/build all OSS components once, then pin versions locally**:
   - Postgres + pgvector (official Docker images, self-hosted)
   - MinIO (official OSS release)
   - unstructured.io / docling as pip packages (vendored into the backend image, not called as a hosted service)
   - No model weights to manage — the LLM is Gemini Flash, called via API, not hosted locally.
4. **No GPU provisioning needed** — this is the one infra requirement that drops out entirely by using Gemini Flash instead of a self-hosted model. Simplifies hardware significantly.
5. **Vault (or encrypted `.env`) provisioned** before any service starts — no service boots with hardcoded or plaintext secrets. Gemini API key lives here, nowhere else.
6. **Docker Compose brings up all services** on isolated internal networks. `llm-gateway` gets a narrow, explicit `ufw`/Docker network egress rule to the Gemini API endpoint only; every other container has outbound internet access disabled at the network level. Nginx remains the only internet-facing entry point for inbound traffic.
7. **Once running: every service except `llm-gateway` operates with zero outbound internet access.** `llm-gateway`'s egress is allow-listed to one endpoint. OS security updates and Let's Encrypt renewal need periodic internet access on the host itself — both scheduled and firewall-scoped narrowly, separate from the application network segments.

---

## 6. Revised 2-Day Phased Plan (open-source, self-hosted)

### Day 1

**Phase 1 (0–2h): Host + Infra Hardening**
- Ubuntu 24.04 base hardening, `ufw`, `auditd`, Docker + Compose install, folder structure scaffolded per Section 3, Vault/secrets provisioned.

**Phase 2 (2–5h): Data Layer + Domain A/C Seeding**
- Postgres + pgvector container up, schema created.
- **Domain A seeding**: ingest the actual Legal Constitution + conflict register documents, run category-discovery pass (derive real category structure from source — do not assume a fixed count), load as versioned structured data.
- **Domain C seeding**: fetch prioritized statute set from India Code (Contract Act, IT Act, DPDP Act, Companies Act), chunk by Section number, embed, load into pgvector + FTS index.
- MinIO up with per-tenant bucket policy, network segmentation verified (`db-postgres` and `storage-minio` have no internet egress — confirm now, not later).

**Phase 3 (5–7h): LLM Gateway Layer**
- `llm-gateway` service scaffolded, Gemini API key provisioned via Vault/encrypted `.env`, egress allow-list configured (this container only, this endpoint only), redaction module stubbed, single `validate_clause(clause, context) → verdict` interface built, smoke-test one API call end-to-end and confirm no other container can reach the internet.

**Phase 4 (7–10h): Ingestion + Extraction Pipeline (Domain B)**
- FastAPI skeleton, upload → MinIO → parse (unstructured.io/docling, local) → clause segmentation with offsets → extraction call routed through `llm-gateway` → structured storage in Postgres.

### Day 2

**Phase 5 (0–3h): Retrieval + Validation + Guardrails**
- Hybrid retrieval function (pgvector + Postgres FTS) built once, reused across all three domains — rules lookup for Domain A, per-doc lookup for Domain B, statute/judgment lookup for Domain C.
- Judgment-tier validation prompt sent through `llm-gateway` to Gemini Flash, guardrail module (citation verification, confidence threshold, cross-ref hard-gate, "no retrieval match → no LLM call" enforcement) — all as testable, isolated code in `backend-api/app/guardrails/`.
- Unified chat endpoint: query → domain router decides which index/indexes to search → retrieve → LLM synthesize with citations, or "Information not found" if retrieval is empty.

**Phase 6 (3–5h): Frontend**
- Next.js **unified workspace UI**: single screen per session — document view (clause-highlighted) + verdict cards (Domain A validation) + chat panel (Domain B/C queries), all available together, not separate tabs. Every answer surface shows citation + confidence, or "Information not found."
- Served via Nginx, no direct internet-facing DB/LLM access — everything routes through the API layer only.

**Phase 7 (5–7h): Security Pass**
- `ufw`/network segmentation audit, Trivy scan on all built images, OpenVAS + OWASP ZAP scan, confirm the **only** egress in the whole stack is `llm-gateway` → Gemini API and every other container is fully sealed, audit log integrity check, confirm Gemini enterprise data-retention terms are signed off before proceeding.

**Phase 8 (7–9h): Eval + Deploy**
- Run the 22-conflict register as live eval set for Domain A, confirm flag-not-guess behavior on known conflicts.
- Run a sample statute-lookup query set (e.g. "what does Section 138 NI Act say") against Domain C, confirm correct Section-level citation and correct "not found" behavior for out-of-scope statutes.
- Smoke test full flow on a real 100-page doc (Domain B), sign off, deploy to production on the same Ubuntu host.

---

## 7. What Claude Code should build first
1. `infra/` — Docker Compose skeleton with network segmentation and folder structure exactly as Section 3, before any application code. Get the egress allow-list on `llm-gateway` right from the start — this is the single hole in an otherwise sealed system, and it needs to be intentional, not incidental.
2. `db-postgres/schema/` — seed with existing Legal Constitution categories and conflict register.
3. `backend-api/app/guardrails/` as its own testable module from day one — this is the security-critical logic and should never be entangled with prompt code.
4. `llm-gateway/client/` — the one interface function (`validate_clause(clause, context) → verdict`) that talks to Gemini. Keep every other service unaware it's Gemini specifically; this isolation is what makes a future swap (self-hosted model, different vendor) a config change instead of a rewrite.
5. Network egress verification script — run it after every phase, not just at the end. It should assert exactly one egress path exists in the whole stack, and fail loudly if a second one appears.

## 8. The one residual risk this design doesn't eliminate
Every other component in this stack is fully open-source and self-hosted — no compromise. The Gemini Flash dependency means clause-level content does leave your infrastructure on every LLM call, and your confidentiality guarantee for that slice of the pipeline rests on Google's contractual terms, not your own control. This is a deliberate tradeoff you've chosen for speed/context-window reasons, not an oversight — just make sure it's stated explicitly to whoever signs off on customer-facing security claims, so no one downstream assumes "fully self-hosted" when one call in the pipeline isn't.
