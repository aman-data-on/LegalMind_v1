# Gemini activation runbook — from key to open gate

**Status: 📁 DERIVED — an operations runbook. It decides nothing**; the gate opens only
by the appended record `AM-31` g3 requires. Prepared 2026-08-27.

The assist lane is complete up to the generated sentence. This runbook is the exact,
ordered path from "nothing configured" to "generated answers on real material", with
who does each step.

---

## Step 1 — Choose the tier and confirm the terms *(owner — the only decision)*

`AM-30` leaves the tier open: **paid Gemini API** or **Vertex AI**. Either is eligible
only with **written** confirmation that the tier does not train on submitted content
(`AM-30` t6, `AM-31` g1), plus its data-retention terms.

* Paid Gemini API: Google publishes the no-training commitment for paid usage in the
  Gemini API Additional Terms — confirm it on the current version of those terms, on
  your account, and record the date.
* Vertex AI: the commitment is part of the Google Cloud enterprise terms.

**What must be recorded: provider · tier · the date you confirmed · where the written
term lives.** Free tiers are ineligible — Google's free-tier terms permit training on
submitted content (t6 makes such a tier ineligible *whatever its cost*).

## Step 2 — Create the API key *(owner or operator)*

1. Google AI Studio (paid tier attached to a billing account) → *Get API key* →
   create key against the billed project. For Vertex AI, use a service-account key
   and the Vertex endpoint (a small adapter change — say so and it will be made).
2. Restrict the key (recommended): API restriction = Generative Language API only.
3. Handle it as a secret: **never** in the repository, a document, or chat.

## Step 3 — Configure the server *(operator)*

```bash
# In the server's environment (systemd unit, compose .env, or secret store):
LEGALMIND_GEMINI_API_KEY=<the key>
# Optional pin override (default: gemini-3.6-flash):
LEGALMIND_GENERATION_MODEL=<pinned, dated identifier — "latest" is refused>
```

## Step 4 — Verify, without touching real material *(operator)*

```bash
cd backend
# Configuration only — no network call:
python3 -m tools.verify_gemini_connection --environment staging
# One synthetic call through the production seam (fixed inert test text, 55.3):
python3 -m tools.verify_gemini_connection --environment staging --live
```

`READY` means: key present, model pinned, gate decision correct, and one grounded
synthetic call returned a cited answer. In **production** the tool reports
`NOT READY` while the gate is CLOSED — that is the correct state, not an error.

## Step 5 — Open the gate *(one reviewed change, on the owner's recorded confirmation)*

Done as **one commit**, per `AM-31` g3 (never a flag or env var):

1. Append the release record to `all_lock.md`: provider, tier, confirmation date,
   where the written terms live (rule 22 — append, never edit).
2. Set `AM31_GATE` in `backend/legalmind/assist/generation.py` to the released value
   named in that record — `tests/test_generation.py` checks the two agree, so a gate
   change without its record fails CI.
3. Update [LOCKED_DECISIONS.md](../00-project/LOCKED_DECISIONS.md) and the status
   documents in the same change.

## Step 6 — Measure what was previously unmeasurable *(engineering, same day)*

```bash
# The deferred half of the Tier-2 quality gate (AM-28): faithfulness and
# citation precision need real generated answers — synthetic substitutes are
# forbidden (AM-31 m4). Run, review, then baseline deliberately:
python3 -m tools.verify_assist_quality
python3 -m tools.verify_assist_quality --write-baseline   # a reviewed act
```

From then on the full gate — retrieval **and** faithfulness — blocks any change to
search, chunking, prompt or model that worsens the recorded bar.

## Step 7 — Confirm the egress posture *(operator, production only)*

`AM-30` t8: network-layer allow-list to `generativelanguage.googleapis.com:443` from
the `api` service only; deny-by-default elsewhere (the compose reference already
gives the document-processing network no route out). The preflight reports this as
an ATTEST item — attest it, don't assume it.

---

**Rollback:** remove the key from the environment → every generation call refuses →
users see the identical `AM-29` r4 refusal sentence; retrieval, citations and the
whole workspace keep working. Closing the gate itself would be a further appended
record plus the same one-commit discipline.
