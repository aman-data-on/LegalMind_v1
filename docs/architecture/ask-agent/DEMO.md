# LegalMind Ask — demo instance (5 October 2026, 09:00 IST)

📁 Demo record — not a specification. Production is untouched: no production database,
key, configuration, deploy or merge is involved.

## Start it

```bash
cd /root/legalmind-worktrees/ask-agent-p0      # branch feat/ask-agent-phase0-1, tag demo-best
backend/tools/demo_start.sh
```

| | |
|---|---|
| URL | http://127.0.0.1:3299 (API on :8299) |
| Login | `counsel@e2e.test` — password in `/root/.legalmind/demo/login.txt` (mode 600) |
| Database | scratch `legalmind_v1_demo` — nothing else |
| Documents | `MSA` (company template), `SLA-leapswitch`, `SLA-cloudpe` (public), `Partner-Agreement-template` (company template, A-76); Legal Constitution, company standards and public statutes as company sources |
| Model | `gemini-3.6-flash` through the free key in `/root/.legalmind/gemini-dev.env`, read into the environment by the script — never in code or logs |
| Agent mode | `LEGALMIND_ASK_AGENT_MODE=on` in this process only; `on` never answers in production (A-81) |

Smoke check in a real browser: `cd frontend && SHOTS=<dir> node scripts/demo-check.mjs MSA
"<question>"` (logs in, opens the document, asks, screenshots the answer).
Before presenting, start every document's Ask clean (the dock reopens the newest
conversation, and a rehearsal's earlier turns would carry forward):
`sudo -u postgres psql -d legalmind_v1_demo -c "TRUNCATE assist.conversations CASCADE"`.
Logs: `/root/.legalmind/demo/api.log`, `web.log`. Stop: kill the two PIDs the script prints
(by PID — `pkill -f` matches your own shell). In a document, open **Ask** at the bottom of
the right-hand panel.

## The script

Five conversations, private at `/root/.legalmind/demo/demo_scripts.json` (synthetic text
only), run with `python3 -m tools.ask_demo --db <demo url> --scripts <that file> --out
/root/.legalmind/demo/runs [--only D1] [--runs 2] [--cached]`.

| | Document | Turns | Languages |
|---|---|---|---|
| D1 | MSA template | data loss and the cap; "our engineer decommissioned the server"; Hindi follow-up | English, Hindi |
| D2 | Partner template | Gold benefits (percentage not stated); one-time affiliates 10 %; cap and "same as our MSA?"; termination and compensation; the 3.3 → 9.2 reference | English, Hinglish |
| D3 | Leapswitch SLA | credit in Hinglish; "it was a CloudPe VM"; claim window and cash; emergency maintenance; company standard vs the SLA | Hinglish ↔ English |
| D4 | MSA template | the 12-month question; the client's "6 months' compensation"; 17.2 vs 17.7 | English only |
| D5 | CloudPe SLA | a pasted synthetic complaint e-mail; "what's your take?"; "draft a reply"; "make it shorter" | English |

**05:40 IST, 5 October: the free key is exhausted for the day** (it served nothing at
05:38). Unless another key is supplied, every answer in the demo is the floor below.
Floor-only, the script passes 2 of 19 turns on critical items; it is strongest on direct
clause questions (D4.1, D2.2, the cap in D1.1) and cannot do arithmetic, language or drafts.

**Verification status — see STATUS.md § Loop log for the latest.** D4 passed all critical
items once (2026-10-04 23:25). The two-consecutive-run bar was **not** reached for any
conversation: the free key's quota ran out (below).

## If the model fails mid-demo

The deterministic floor answers: the clauses of the selected document that match the
question, quoted verbatim and cited, with one line — "The full assistant could not complete
an answer just now; these are the passages that match your question, quoted from the
sources." No blame, no dead end. Verified in the browser with the quota exhausted: the
cap question returned 17.7 and 17.2 (with its six-month rule) in 0.7 s.

## KNOWN LIMITATIONS

0. **Google's free tier is busy at times (HTTP 503).** One retry recovers most; when
   both fail, that answer is the floor (one line and the clause that answers). Asking
   again a minute later usually gets the full answer.

1. **Quota.** The free key allows **20 requests per day per model** on `gemini-3.6-flash`.
   A turn takes 1–4 requests (one when no search is needed, since the answer-now
   path), so a day's quota covers roughly 8–12 turns. Key Obligations extraction is
   switched off in the demo instance (`LEGALMIND_OBLIGATIONS_EXTRACTION=off`) so opening
   a document spends nothing; its panel says the obligations could not be extracted. The quota resets around
   05:30 IST. When it runs out, every answer is the floor (quoted clauses), not an
   explanation. A paid key, or billing enabled on this key's project, removes the limit.
2. **Not verified twice.** No demo conversation has passed all critical items in two
   consecutive runs; D4 passed once. Treat any unrun turn as unproven.
3. **Latency.** Each call is 2–6 s, and a turn is 10–25 s. Back-to-back turns hit the
   free tier's per-minute limit and wait (one turn took 49 s). Pause between questions.
4. **Another document by name.** When the reader names a document other than the selected
   one ("it was a CloudPe VM"), the agent must find it with its own search; this is the
   part least measured (4 of the 41 needed items depend on it).
5. **Hindi in Devanagari.** Cited claims stay in English (the claim checker reads English);
   the explanation is in Hindi. A Hindi sentence that names a party in Devanagari can be
   withheld by the party check, which fails closed (AM-69); the reply then says one
   statement was left out.
6. **Source labels.** Citations show evidence keys ("D176: 17.2, the selected document"),
   not page links; the original PDF panel may load slowly — the Text tab is reliable.
7. **No company data-loss position.** The intended data-loss position is not in the
   sources (owner ruling); answers say so rather than state it.
8. **Floor ranking is by words.** When the model fails, the third quoted clause can be
   loosely related (an indemnity clause beside the cap).
