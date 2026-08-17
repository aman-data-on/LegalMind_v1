# Authentication

> **Step 47 supersedes this file's open items.** The identity contract, session model and revocation are specified in [STEP_47_SECURITY_SPECIFICATION.md](STEP_47_SECURITY_SPECIFICATION.md) §47.1. The authentication *mechanism* remains escalated as **OD-9**.


Canonical source: `all_lock.md` (Step 43.3 `auth` module; Step 39 "Security")

**Status: PARTIALLY SPECIFIED.** The *responsibilities* of the authentication layer are locked (Step 43). The *implementation mechanism* — identity provider, session vs token strategy, password/SSO policy, integration with any existing corporate authentication or API — is explicitly listed among the not-yet-locked decisions in the master specification.

---

## Locked — responsibilities of the `auth` module (Step 43.3)

**Status: LOCKED**

Responsibilities:

```text
Authentication
User lookup
Role resolution
Permission checks
Session/token validation
```

It should answer:

```text
Who is this user?
What role do they have?
Are they active?
```

It should **not** decide legal outcomes.

---

## Locked — authentication precedes authorization

**Status: LOCKED**

Authentication is the first stage of the locked server-side security boundary:

```text
Authentication → Authorization → Business Operation → Database
```

Authentication answers *who the user is*. It never answers *what they may see or do* — that is [AUTHORIZATION.md](AUTHORIZATION.md) and [OWNERSHIP.md](OWNERSHIP.md). Knowing an object's ID is never sufficient for access; see [SECURITY_MODEL.md](SECURITY_MODEL.md) §5.

---

## Recommended controls (Step 39)

**Status: RECOMMENDED (not yet locked)**

The Step 39 security checklist includes `TLS`, `Authentication`, `Session security`, and `Secrets outside source code`. The full checklist lives in [SECURITY_MODEL.md](SECURITY_MODEL.md) §8 and is not duplicated here.

---

## NOT YET SPECIFIED

The following authentication decisions are explicitly open in the master specification and must **not** be assumed during implementation:

* Authentication implementation (mechanism, library, protocol)
* Whether LegalMind integrates with an existing authentication system or API
* Session vs token lifetime and refresh policy
* Password policy, MFA, or SSO/IdP selection
* User provisioning and deactivation workflow

Do not invent these. They require an explicit specification step and approval.
