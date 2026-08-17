# Deployment

> ⚠️ **Superseded.** Deployment is now specified and 🔒 LOCKED by **Step 55** — see [STEP_55_DEPLOYMENT.md](STEP_55_DEPLOYMENT.md), which is authoritative and answers most of the "NOT YET SPECIFIED" list below. This file is retained as the record of the earlier Step 39 recommendation.

Canonical source: `all_lock.md` (Step 39 "Deployment")

**Status: RECOMMENDED (not yet locked) — as of Step 39.** The source presents the deployment shape below as a recommendation. Nothing has been deployed.

---

## Recommended V1 deployment shape (Step 39)

For V1, keep deployment relatively simple:

```text
                    Internet
                       ↓
                  Reverse Proxy
                       ↓
              Next.js + FastAPI
                       ↓
            ┌──────────┴──────────┐
            ↓                     ↓
       PostgreSQL          Background Workers
                                  ↓
                                Redis
                                  ↓
                           Object Storage
```

You don't need Kubernetes on day one.

Docker Compose can be enough for development and potentially a small production deployment; production orchestration can evolve based on actual load and availability requirements.

---

## Related locked constraints

The deployment shape must respect these locked architectural decisions — see [SYSTEM_ARCHITECTURE.md](../05-architecture/SYSTEM_ARCHITECTURE.md):

* V1 is a **modular monolith**; the specification explicitly states what should *not* be split into microservices (Step 38.26).
* Analysis runs as **background/async processing**, not inline in the request path (Step 38.19, Step 43).
* The security boundary is server-side and must not be bypassed by the deployment topology (Step 38.21) — see [SECURITY_MODEL.md](../06-security/SECURITY_MODEL.md).
* Storage responsibilities are split between PostgreSQL and object storage (Step 39) — see [STORAGE_ARCHITECTURE.md](../05-architecture/STORAGE_ARCHITECTURE.md).

---

## NOT YET SPECIFIED

* Environments (dev/staging/production) and promotion process
* CI/CD pipeline
* Secrets management mechanism (Step 39 lists "secrets outside source code" as a control, not a mechanism)
* Monitoring/alerting specifics beyond the stack table entry
* Backup and disaster-recovery runbook
* Scaling, availability, and load targets
