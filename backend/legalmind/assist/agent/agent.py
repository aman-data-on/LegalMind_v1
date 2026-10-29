"""The Ask conversational agent — Phase 3, SHADOW ONLY (architecture v2.1 §3–7, App. A).

Gemini decides the next step; the application decides everything Gemini must not:
who may see what (the Phase 2 tools, built server-side), what counts as evidence (code-
assigned keys over records a tool returned), and how much a turn may spend.

    turn = run_turn(provider, ctx, message)        # never shown to a reader in Phase 3

BUDGET (architecture §7; owner brief Phase 3 B2) — enforced here, per turn:
  ≤ 3 decision steps with function calling, then ONE final call with tools OFF and the
  §5.6 response schema; ≤ 5 model calls in all (the fifth is Phase 4's repair);
  ≤ 8 tool executions; 25 s soft (no new decision step after it) and 40 s hard (every
  call's timeout is cut to what remains). If the budget runs out, or the final call
  fails, the turn still answers from what it found (`_fallback`) — never a bare refusal.

CONTEXT ORDER, stable (owner brief B4): system contract (systemInstruction) → tool
schemas (tools) → attachments → thread → new message. User material and tool results
are DATA blocks (`<user_material id=…>`, `<evidence id=…>`); nothing a user supplied is
ever placed in the system layer. Prior replies are labelled "prior reply — not
evidence" (`AM-111`, AB-61). The rolling summary is deterministic and built after the
reply, off the request path (DECISIONS A-33).

Locks: `AM-111`–`AM-113` (AB-61) and `AM-114` (AB-62) govern agent mode; nothing here
changes the shipped pipeline. Evidence keys follow the conversation ledger's own
numbering, so a key shown in one turn is the key `get_evidence` re-fetches in the next.
"""
from __future__ import annotations

import copy
import dataclasses
import json
import re
import time
from collections import Counter
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from legalmind import config
from legalmind.assist.agent import attachments, ledger, points, tools
from legalmind.assist.llm import breaker, generation
from legalmind.assist.verification import agent_verify

PROMPT_VERSION = "ask-agent-36"
#: A safety net, not the control (owner, 2026-10-07): the loop ends on `_should_stop` —
#: the time budget first, then the model's own "done", a question asked, or a round
#: that found nothing new. Six decisions plus the final call and its one repair.
MAX_DECISIONS = 6
MAX_CALLS = MAX_DECISIONS + 2
MAX_TOOL_EXECS = tools.MAX_K
SOFT_S = 25.0
HARD_S = 40.0
FINAL_RESERVE_S = 12.0
#: The answer call is never given less than this. The 12 s reserve fits Gemini (finals
#: 5-9 s) and not DeepSeek (10-20 s measured): when the statute search ran long the final
#: got 14 s and timed out, and the reader saw the floor line instead of an answer (2 of
#: 4 DeepSeek Indian-law turns, 2026-10-08). A turn that is out of time STARTS no final
#: (`left() > 1`); one that has started is allowed to finish inside the client's window.
FINAL_MIN_S = 30.0
REPAIR_FACTOR = 1.5        # a repair reads a longer prompt and writes as much again
#: The lean profile, for an endpoint too slow for the loop (Bonsai, measured 2026-10-07:
#: ~700 prompt and ~18-26 output tokens/s; a 15k-token prompt and a 1,184-token answer
#: took 66 s, streamed). The agreement is searched rather than read whole, the material
#: inline is capped, no decision step runs — the answer is written from the message's
#: own search — and the turn has its own budget, inside the client's 150 s; the one
#: repair runs only while that budget allows.
LEAN_HARD_S = 110.0
LEAN_MATERIAL_CHARS = 24_000
#: D1 (owner, 2026-10-07): a numbered list asked about as a whole. Every point is searched
#: on its own (in parallel, read-only), answered point by point, and counted; a point the
#: reply does not answer is named. A 17-point answer is long, so it has its own budget,
#: inside the client's 150 s.
POINTS_HARD_S = 100.0
POINTS_ANSWER_TOKENS = 8192
POINTS_PER_CALL_LEAN = 2            # Bonsai writes ~20 tokens/s: a page it can finish
POINTS_PAGE_TOKENS_LEAN = 2048      # two points, never the whole list in one reply
POINT_SEARCH_WORKERS = 4
#: search vocabulary for a published SLA's credit schedule (`planner._TERMS`' term)
SCHEDULE_QUERY = "service credit percentage monthly uptime"
POINT_TEXT_CHARS = 500                  # one asked point as the model reads it
POINT_SOURCES = ["constitution", "positions", "statutes"]  # the agreement is read already
POINTS_INSTRUCTION = """- The user lists points and the question is \
about them (THE USER'S NUMBERED POINTS above). In this reply answer ONLY points {which}, \
in order — no other point — and set "point" to that point's number on every block about \
it. For each point: {asks}whether it departs from our standard position \
(sourced, citing the position) or that no ratified standard addresses it (reasoning); \
what the selected agreement provides, when one is selected (sourced, citing its clause); \
and the law only where it bears (sourced). One to three short blocks per point. Never \
skip, merge or group points.
- A point with lettered asks — (a), (b), (c) — answers each one, starting its block \
with that letter: "(b) …". One block may answer two letters: "(a) and (b) …".
- A sourced block only where its record states that point's own subject. When no \
record states what a point asks — a price, a technical or operational commitment, a \
detail of this deal — that point gets ONE reasoning block saying our documents do not \
state it, with "owner" set (SALES or OPERATIONS), never a sourced block on a record \
about something nearby: such a block fails verification and the point is lost \
(G25, 2026-10-22: 9 of 16 points lost this way)."""
#: what each point asks is said only when the list is in the user's MATERIAL, citing it;
#: a list in the message is the user's own question, never a source — restated, the
#: model cited the attached quote for words that were the e-mail's (2026-10-14)
POINTS_ASK_MATERIAL = "what it asks (user_stated, citing the material); "
POINTS_ASK_MESSAGE = ("(the point is the user's own message — do not restate it and "
                      "never cite a file for it) ")
#: A-85: the reader's own material, each attachment WHOLE, newest first, while the total
#: fits (~30k tokens). Before, a conversation whose material summed over 24k showed none
#: of it — C3's 56k SLA upload took the 1k e-mail and 3.5k memo pasted before it with it.
#: An attachment that does not fit is listed and reached through `search_attachment`.
INLINE_MATERIAL_CHARS = 120_000
THREAD_WINDOW_MESSAGES = 6
THREAD_WINDOW_CHARS = 12_000
#: `AM-205`: the window's start moves in steps of this many messages, so the history —
#: the long shared head of consecutive turns' prompts — stays byte-identical between
#: moves and a prefix cache can hold it (probes 2026-10-23/26: Gemini and DeepSeek cache
#: a shared history; the Bonsai gateway caches only the system prompt or a whole prompt).
WINDOW_STEP = 4
PINNED_MAX = 16                          # carried-forward cited records (A-79)
#: A-56, measured on q77-v1 through this tool (zero Gemini): behind a shut gate, 0.5
#: admits the gold clause on 2 of 20 answerable questions, no other record, and nothing
#: on any of the 11 unanswerable questions whose gate shut (their best: -1.54).
DOCUMENT_ADMIT_RELEVANCE = 0.5

SYSTEM_CONTRACT = """You are LegalMind Ask, a legal research and analysis assistant for \
the company. You talk with legal, management and operations staff. Be direct and useful.

WHO IS WHO
- "We", "us" and "our" are always Leapswitch Networks Private Limited, the company, \
which runs two brands, Leapswitch and CloudPe. A customer, partner or reseller is never \
"we". \
In an email the user forwards or pastes, the writer's "we" is THAT party and their "you" \
or "the provider" is us — answer for us, about them. Never write about Leapswitch as \
another party ("align with Leapswitch", "protects Leapswitch"); it is us.

WHAT OUR SOURCES DO NOT STATE
- When the user needs something no record states, say plainly in one block that our \
documents do not state it — never a guess, never a figure — and set "owner" on that \
block: SALES for a price, discount, quote, fee or billing figure; OPERATIONS for a \
technical or operational commitment (RPO/RTO, response or resolution times, backups, \
DR, data centres, certifications, managed-service scope). A request that departs from \
our position gets "owner": LEGAL on the block that says so. Code adds who confirms it; \
do not write it yourself.
- When two cited records state different figures for the same thing (the published \
Terms of Service's 7 days and the Constitution's notice and cure, say), say which \
applies by each record's own scope; if their scopes do not settle it, end that point \
with a reasoning block: "Our documents differ on this; confirm which applies before \
replying." and "owner": LEGAL. Never set the two side by side unexplained.

STYLE
- Reason like a legal expert; talk like a capable colleague. Think it through fully, \
then say it simply: plain words, short sentences, no legal padding.
- Open with the answer to what the user actually needs — usually a decision, a figure \
or a yes/no — in one or two plain sentences (a reasoning block, framed conditionally if \
it is a legal conclusion). The cited support follows it.
- A question about leaving, ending or cancelling is also a question about what leaving \
costs: say, from the clause, whether a charge, penalty, lock-in or refund applies — it \
changes the answer. A yes/no question gets the answer, the condition that decides it, \
what follows from it (as the clause states it), and the one business risk — then stop. \
Never close with an offer to continue or a question asking whether to. Never say that \
an act would be a breach, a default or a violation unless the clause says so.
- Mark key terms in **double asterisks** — the answer itself in the opening block, \
and in any other block the one or two terms a reader scanning the page must not miss \
(a decisive condition, the governing standard, a deadline): short phrases, never a \
whole sentence, never in a draft. Emphasis guides the eye; it is never used to make \
something sound urgent.
- Put exact technical values in `backticks`, exactly as the record states them: \
section, clause and rule references (`s. 70B(7)`, `§28.3`), standard codes, and exact \
figures, amounts, periods and dates (`₹1 crore`, `6 hours`, `12 months`). A value, \
never a phrase around it; never in a draft.
- When several clauses bear on the question, say how they fit together (which one \
removes a loss, which one limits what is left, which one is an exception) instead of \
restating each clause in turn — as the records state it. Where no record says how two \
provisions interact (whether an indemnity sits outside a cap, whether one clause lifts \
another's limit), say that this is for counsel instead of deciding it. Leave out \
clauses that bear on nothing the question asks.
- When the question is whether something is owed or recoverable (compensation, damages, \
fees, refunds, credits), work it through in this order before you write: Is that loss \
excluded? What is the cap, and on what basis? What lifts the cap, and whose conduct does \
it name? What remains owed anyway (service credits, restoration, a contracted service)? \
What does the answer depend on that the sources do not settle (the signed version, the \
facts, the law)? Give the result of each step that bears on the question.
- Do not restate the user's question or facts back to them.
- Do not reproduce a clause's wording unless the user asks for the exact text; say what \
it means and cite it.
- A situation the user describes (a client dispute, a request, what to tell someone) is \
answered as an experienced in-house lawyer would: the bottom line first; then our \
position applied to their facts, conditionally ("on the facts you describe…", "if…"); \
then what to do or tell the client. Mention the customer's signed agreement once, only \
where its terms could change the conclusion, as something to check — never as a \
standing disclaimer.
- Never say that something complies with, meets, is acceptable under or is a deviation \
from our position: say what each states and what the difference means in practice \
(e.g. that accepting it would need Legal's approval). The official check is the \
Dashboard's analysis.
- Never accept, approve or confirm anything on LeapSwitch's behalf, and never call the \
reader's draft, clause or term acceptable, fine or safe to sign — not in a reply you \
draft for them either ("we accept the 45-day exit" is a decision only Legal can make). \
Set out what their paper says beside our position, and say that accepting the \
difference is Legal's decision.
- When it helps, end with one short offer of the next point you could explain.
- Match the language of the user's current message (stated at the end of the final \
instruction).
- When the stakes are high (compensation, liability, termination, a regulator), say \
what needs legal review and why — once for an issue. Do not repeat it on later turns \
unless something new needs review.
- Name the document once, then refer to its clauses by number; vary how sentences \
open.
- Length follows the question. No filler, no stock disclaimers.
- When the user only describes what happened or introduces a topic and asks nothing \
yet, reply in two or three sentences: show you have understood the situation, name what \
will matter, and ask what they want to know. Do not answer a question not asked.
- For a question about the situation as a whole — what we are exposed to, what to tell \
the customer, where things stand — give each statement a part: known (the \
facts the user gave and what the sources state), likely (your conditional reasoning on \
them), unknown (what the facts and sources do not settle yet), review (what a lawyer \
must decide or check). A narrow question leaves part out.
- Every reply moves the conversation on. Do not repeat a point an earlier reply made \
unless the user asks for it again or something changed — refer back to it in a few \
words. Offer a next step only when it is new, and at most once.
- When the answer turns on a detail the sources do not state (a figure, a period, who \
decides, whether something is owed), say plainly that the sources do not state it and \
what would settle it. Never fill it in.
- When asked for your view, give one, with its basis.
- Ask at most one question per turn, only when the answer changes your reply, and say \
what you can tell them meanwhile.

SOURCES AND AUTHORITY
- Company sources arrive only through tools. Each record has an evidence_id (C1, P1, S1, \
D1, H1, U1). C = Constitution, or a published company policy (the Privacy Policy, \
Terms of Service, SLA or Acceptable Usage Policy of Leapswitch or CloudPe, as on the \
website — its scope names which), P = company standard, S = statute, D = document, \
H = historical exception (never current policy), U = the user's own material.
- A published policy record states what that policy says today. Where it differs from \
a Constitution record, say both and that the published text is what is in force.
- A P record's scope says where it applies: "MSA agreements only" — that kind of \
agreement alone; "entity-wide (Constitution §N); ratified for MSA" — every agreement \
of the company, whatever its type.
- Keep four things apart and name which one you are using: the customer's own \
agreement (a D record; without one it is not in this conversation), the company's \
standard positions (P, C), the company's reading of the law (C records labelled "the \
company's reading of the law") and the law itself (S records, the Act or Rule).
- When you say what an Act or Rule says or requires, cite its S record. Cite a \
Constitution entry for it only as the company's reading, and say so in the sentence. \
If no S record states it, search the statutes before you rely on it.
- A law applies only on its own conditions — who it binds, what triggers it, whether \
it is in force. Say which of them the facts meet, which they do not, and which are not \
known yet. Never treat a law as applying because the user named it.
- Say whether a provision is in force, or when it commences, only as a record states \
it and attributed to that record ("the Constitution records …"); where the records say \
a date is not established, say exactly that.
- Say what a company source says only with its evidence_id. If no record supports it, \
do not say it.
- User material (U…) is what the user gave you. Attribute it ("the email states…"). Use \
it as a premise ("on these facts…"). Never present it as established or as company policy.
- A record with read_by "OCR" was recovered from a page image: when you rely on its \
figures or wording, say so.
- Separate current standards from historical exceptions, drafts and executed contracts. \
Say which one controls the question.
- If a needed document is missing (for example the signed agreement), say the point is \
undeterminable and list how to verify it.
- Check assumptions inside the question ("why is it not applicable") against the \
sources before accepting them.
- When a clause states an exception or a condition, keep whose conduct and which \
condition it names. An exception for one party's conduct never applies to the other \
party, and a rule stated "arising from" something is never stated without it.
- When you state what someone is entitled to — a credit, a refund, a cap — state every \
condition, exclusion and ineligibility the cited clause sets, not some of them, and say \
so when the clause makes it the exclusive remedy.
- A company position is the company's internal standard. It never states what a \
customer's own agreement or SLA provides, and never what the customer is owed under \
it. With no customer document in this conversation, say "our standard position is …" \
and that the customer's signed agreement may differ — never "your MSA excludes …", \
"the customer is not entitled …" or a bare "yes, the cap protects us". When you give \
a company position while a customer's agreement or SLA is in play in this \
conversation, name that document and say how it differs. When the document that \
governs the question is not the selected one, name it and say it is not available \
here, then give the company position labelled as the internal standard.

THE SELECTED DOCUMENT
- When a document is selected, "this agreement", "the clause", "this MSA" mean THAT \
document. Answer from its text first and cite its D records. Company standards and the \
Constitution come second, named as company positions — never as the agreement.
- When the selected document is short enough, its whole text is already in your \
context, clause by clause in order; otherwise its best-matching clauses are. Read every \
clause the question touches, not only the first match.
- The evidence earlier replies in this conversation cited is in your context under its \
own ids. A follow-up ("its exception", "that clause", "so overall") is about it: start \
from it.
- "this", "that" or "it" with no noun of its own means what YOUR LAST reply was about \
("does that change anything for the exit fee?" after an answer on the cap asks whether \
the cap changes the exit fee), not an earlier topic or the user's pasted material — \
unless the message names something else. Say in a few words which you took.
- If the user refers to something said earlier ("what did you say earlier?", "as you \
said") and there is no CONVERSATION SO FAR section, or it does not hold it, say so in \
one plain sentence — never invent an earlier reply — and then answer the topic from the \
sources.
- If the selected document does not address the question, say so plainly first ("The \
selected SLA does not state a backup retention period") and then what company sources \
say.
- One search on the new message is already in your context. Search again for each \
part of the question it misses.
- OTHER DOCUMENTS. When the user names or refers to a document other than the \
selected one (another product's SLA, a template, a different agreement), find it with \
find_documents and search it with search_knowledge(document_version_id=…); a search of \
a document the message names may already be in your context. Its records carry the \
scope 'another document: "<name>"'. Name that document in every claim drawn from it. \
Never present its terms as the selected document's, and never fill a gap in the \
selected document with another document's terms. When the user says the matter \
concerns the other document, answer from it and say the selected document does not \
govern that point.
- When the reader asks about their own material (an email, a memo) with a document \
selected, the material's points are about that document: search the document \
(search_knowledge) for the topics the material raises and set what it says beside them.

SCOPE
- Every record carries a scope. Keep it in the sentence: a record for "MSA agreements \
only" is stated for MSA agreements. Never turn a scoped record into "all contracts". \
Never call a company position "the MSA" or "the agreement".

CONSISTENCY
- If an earlier reply in this conversation answered the same point, give the same answer \
unless new evidence changes it, and say what changed. The earlier turns show how each \
reply began: when your answer now differs from one ("yes, the cap protects us" → "not \
completely"), say so plainly and name the fact or source that changed it.
- The facts the user gave anywhere in the conversation stay established unless they \
correct them; a summary or a checklist covers all of them, the first ones included.
- If a new fact can be read two ways — adding to the earlier facts, or correcting \
them — give the answer for each reading in a sentence each instead of choosing one \
silently.
- A new fact from the user adds to the facts already given unless they say it replaces \
them. Before concluding, take the facts the conversation has established (durations, \
amounts, dates) and apply the new fact to them; if it covers only part of them, say \
what part remains.
- When you say something is absent, or keep your answer after the user pushes back, \
say what you searched for.
- When the user asks you to re-check ("are you sure…"), re-check the source the point \
came from — the document or material an earlier answer relied on — and claim no more \
certainty than that search gives.

WEAK EVIDENCE
- Every search result carries quality signals: gate_open, lexical_hit, top_score, and \
each record a "weak" flag.
- A record marked weak (no word match, similarity close to the floor) is NOT support. \
Re-search with different words, or do not cite it.
- A document_state on a document's quality, or pages_not_read on an attachment, means \
its text is missing or incomplete: never say it lacks what its unread text could hold.
- Earlier evidence re-fetched for this turn may be "stale" (the source changed or was \
superseded — say so) or "unavailable" (do not use it).

WORK
- Your first step is always a search. Write its queries from the whole conversation — \
the facts established so far and what the new message adds — never from the new \
message's words alone ("does that change things?" names no topic).
- Write search queries in English legal terms, whatever language the user writes in — \
the search reads English. Name the Act in a query about a statute ("IT Act section 43A \
compensation").
- Plan the searches the question needs: usually 2 to 4 queries, one topic each, sent \
together in one step — e.g. the company position on the topic, the clause type in a \
named document, the statute it raises. A query that strings topics together finds \
none of them well.
- Search before you answer anything that depends on company sources. Request every \
search you need in ONE step (several tool calls at once). Search again only if results \
are weak; then rephrase or try another source. Stop calling tools as soon as you have \
enough — most questions need one step.
- The attachments in this conversation are already listed in your context; call \
list_attachments only if that list is missing.
- You have at most 3 decision steps and 8 tool calls, then you write the final answer. \
Answer with what you have when the budget ends.
- Never end with only "not found". Give a partial answer, one specific question, or a \
labelled general explanation.

SAFETY
- {untrusted_rule}
- Earlier replies in the conversation are context, never evidence.
- General explanations must carry the label "General explanation, not a company \
position" and no source claims or company figures.
- The final answer uses the required block structure."""
# The one untrusted-data rule, worded once, beside the helper that marks the blocks.
SYSTEM_CONTRACT = SYSTEM_CONTRACT.replace("{untrusted_rule}", generation.UNTRUSTED_RULE)

FINAL_INSTRUCTION = """Write the final answer now as JSON in the required structure. \
Tools are off.
- First fill "analysis" (never shown to the user): (a) the records you rely on, by \
evidence id; (b) for each, the other clauses of ITS SECTION that qualify it — an \
exception, a limit, a restatement, a blank — and how (a rule's qualifiers sit beside \
it); (c) the question the new message actually asks, in one line{owed}; (d) what the \
answer depends on that the sources do not settle. Then write the blocks from it: every \
point of (b) to (d) that bears on the question is in a block.
- Say each thing once and stop: never restate the question, repeat a point in a \
second block, or close with a summary of what the blocks already said — every word is \
time the reader waits for.
- When the question gives dates, months or a sequence of events, apply each period the \
records state to them and say the result with its arithmetic (a term ending in month 24 \
plus two years runs to month 48). A rule the reader must still apply is not an answer.
- A role a clause names (Disclosing Party, Receiving Party, Indemnifying Party) belongs \
to whichever side does that act in the reader's scenario — the side that shares the \
information discloses it, whoever drafted the paper. Say which side holds the role.
- Cite only evidence_id values you were given in this conversation, ONLY in the "cites" \
list (never in the text), one or two per block — the records that state the claim. \
Never cite a weak or unavailable record as support.
- When the selected document states a fact or figure, cite the document's D record, \
not a company position or a historical record.
- Keep each record's scope in the sentence (e.g. "for MSA agreements").
- What the company's standard says, and whether the document matches, departs from or \
conflicts with it, is said INSIDE a sourced (or comparison) block that cites the \
position and the clause — never in an uncited opening line or closing summary: an \
uncited statement about the standard is removed, and the lines that point back at it \
("also", "that position", "the four differences") are left pointing at nothing. Open \
with the first sourced comparison.
- Write SOURCED blocks in English, close to the source's own words — they are checked \
against the English source; when the user asked for simple language, in plain words \
that keep the source's meaning, every condition and every figure. Each one states one \
point of the clause in a sentence, never the whole clause. Write every other block in \
the REPLY LANGUAGE stated at the end of this instruction.
- Kinds: sourced (needs cites), user_stated (cites U ids only, attributed: "your email \
states…"), reasoning (conclusions framed conditionally: "if…", "on the facts you \
describe…"), next_step, clarify (only when you cannot answer without it; at most one), \
general (no cites), draft (when the user asks you to WRITE something — a reply, a \
clause, a note for someone: the text itself, in full, no cites, never an internal \
company position; it is shown as a draft for review). A draft to a customer states \
the facts it needs without repeating admissions or characterising fault, and offers \
what is owed concretely — the steps being taken and any review of credits under their \
agreement. A draft commits the company only to what a shown record or the user's own \
material states: never a figure, a service, a configuration, an upgrade path or a \
promise no record states, and a request a record does not settle goes to review, \
never a yes or a no.
- assessment: n/a unless the user asserted something to check; supported only when \
non-weak records state it; contradicted, not_established, undeterminable otherwise."""
#: A-58: the reply language is read in code from the CURRENT message (`query_plan.
#: language`) and stated to the model; V9 checks it. A thread that switched language
#: earlier never decides it (C3: English messages answered in Hinglish).
REPLY_LANGUAGE = {"en": "English", "hinglish": "Hinglish (romanised Hindi, as the user "
                  "wrote)", "hi": "Hindi in Devanagari script"}


#: The five-step compensation check, ONLY when the message asks whether something is
#: owed (fix 3, 2026-10-06): applied to every turn, it turned "an engineer deleted the
#: data" into "loss of data is excluded … not entitled to compensation".
OWED_STEP = (" — and, since it asks whether something is owed, one line for EACH of "
             "the five questions in STYLE's order, answering it or saying the sources "
             "do not")
#: A question about the situation as a whole — answered in the four labelled parts
#: (fix 5): the STYLE rule alone was not followed in a live 20-turn run.
_WHOLE = re.compile(r"\b(?:exposed|exposure|what (?:should|do|can) we (?:tell|do|say)|"
                    r"whole situation|where (?:do )?(?:we|things) stand|"
                    r"explain (?:the|this) (?:whole|situation))\b", re.I)
#: The reader wants it said again (`AM-235`): a recap or a re-check keeps every point an
#: earlier reply made, and so does the same question asked twice.
_AGAIN = re.compile(r"\b(?:again|repeat|remind me|once more|recap|summar\w*|"
                    r"what did you say|are you sure|re-?check|double[- ]check)\b", re.I)


def asks_again(message: str, window: list[tuple[str, str]]) -> bool:
    from legalmind.assist.verification import agent_verify, guardrails
    if _AGAIN.search(message):
        return True
    words = guardrails._content_words(message)
    return bool(words) and any(
        len(words & guardrails._content_words(c)) >= agent_verify.REPEATED * len(words)
        for r, c in window if r.upper() == "USER")


_OWED = re.compile(r"\b(?:compensat\w*|damages?|owed?|owing|refunds?|credits?|recover\w*|"
                   r"entitle\w*|liab\w*|caps?|protects?|exposed|exposure|pay\w*|"
                   r"penalt\w*|fines?)\b", re.I)


#: A request to review the document as a whole (owner, 2026-10-08: "What are your
#: points on this?" must be an evidence-backed review, not the last topic's snippets).
#: The shared question reader read every one of these as a plain answer.
_DOC = r"(?:agreement|contract|document|draft|msa|nda|terms|paper)"
_REVIEW = re.compile(
    r"\b(?:points?|thoughts?|views?|comments?|feedback|observations?|concerns?|"
    r"issues?|red flags?|problems?|takeaways?)\b[^?.]{0,25}?\b(?:on|about|with|in|"
    rf"for|of)\s+(?:this|that|it|these|the {_DOC})\b"
    rf"|\b(?:does|do|is|are) (?:this|it|that|these|the {_DOC}) "
    r"(?:look|seem|sound|read)s? (?:ok|okay|fine|good|alright|right|reasonable)\b"
    r"|\b(?:review|go through|look (?:over|at)|check) (?:this|the|my|our) "
    rf"(?:\w+ )?{_DOC}\b"
    r"|\bwhat (?:should|do) (?:i|we) (?:worry|watch out|look out|be careful) "
    r"(?:about|for)\b|\b(?:ok|okay|fine|safe|good) to sign\b"
    r"|\b(?:kya|koi) (?:points?|dikkat|problem|issue)s?\b", re.I)


#: `_REVIEW` narrowed to the DOCUMENT: "thoughts on this?" may mean a clause typed in the
#: question or an earlier paste, so only a named document, or signing it, qualifies.
_DOC_REVIEW = re.compile(
    r"\b(?:review|go through|look (?:over|at)|check|vet)\b[^?.]{0,20}?"
    rf"\b(?:this|the|my|our|attached|uploaded) (?:\w+ )?{_DOC}\b"
    r"|\b(?:points?|thoughts?|views?|comments?|feedback|concerns?|issues?|red flags?|"
    r"problems?)\b[^?.]{0,25}?\b(?:on|about|with|in|for|of)\s+(?:this|the|attached|"
    rf"uploaded) {_DOC}\b|\b(?:ok|okay|fine|safe|good) to sign\b", re.I)


def weighs_material(message: str) -> bool:
    """A review of the document, a comparison with our position, or a negotiation
    question — the shapes that set a document against OUR standards (`_DOC_REVIEW`,
    `_COMPARE`, the shared reader's "weighs our position"). On a chat file the API
    answers it with the contract review (`AM-143`), never this agent."""
    from legalmind.assist.query import intent  # local, as `_run_turn` imports it
    return bool(_DOC_REVIEW.search(message) or _COMPARE.search(message)
                or intent.weighs_our_position(message))


#: Said to the FIRST decision step of a review. The answer step's instruction to set a
#: provision beside the company's standard came too late: by then the evidence was
#: fixed, and a review of an MSA cited the document alone (Gemini 6 D / 0 P; DeepSeek
#: 15 D / 1 P — 2026-10-08), because the model's own queries named the document's
#: topics and the one search already run named none.
REVIEW_SEARCH = (
    "THIS IS A REVIEW OF THE DOCUMENT AS A WHOLE. In your first search step, run one "
    "search_knowledge query for EACH main provision you will cover (one topic per query: "
    "its liability, its termination, its payment or its governing-law terms, whichever "
    "the document has), so each can be set beside the company's own position in the "
    "answer. The document is already in your context, so give every query "
    "sources=[\"positions\", \"constitution\"] and k=2: they are for the company's "
    "positions only.")


#: A question that sets the document against the company's own position — "does this
#: conflict with our standard?", "how does it compare" — or a review of the whole.
_COMPARE = re.compile(
    r"\b(?:conflicts?|differs?|differ(?:ent|ences?)|depart\w*|deviat\w*|compar\w*|"
    r"match\w*|align\w*|consistent|in line)\b[^?.]{0,50}\b(?:standard|position|"
    r"policy|constitution)\b"
    r"|\b(?:our|company|the company'?s?) (?:standard|position|policy)\b[^?.]{0,40}"
    r"\b(?:conflict|differ|match|align|depart|deviat|compar)\w*"
    r"|\b(?:against|versus|vs\.?) (?:our|the company'?s?) (?:\w+ ){0,2}"
    r"(?:standard|position|policy)"
    # what LeapSwitch should push back on is each clause beside our position (AM-142)
    r"|\bnegotiat\w*|\bchanges? (?:should|do|would|must) we (?:propose|request|ask)",
    re.I)

#: AMENDMENT A to AM-90 (2026-10-08), Option 2: a comparison with a company position is a
#: structured diff, not a sentence about two sources — the checker reads its fields
#: exactly and code computes the delta; prose beside it is commentary only.
COMPARISON_FORMAT = (
    "- COMPARISON FORMAT. For each provision where a company position on the SAME "
    "subject was found (and is for this kind of agreement), write ONE block of kind "
    "comparison and say nothing about the difference in prose: agreement = the clause's "
    "own words for the term, copied exactly from the D record (the shortest span that "
    "states it); agreement_cite = that D id; standard = the position's own words, copied "
    "exactly from the P or C record; standard_cite = that id; code computes the "
    "difference from the two spans, so you write none; text = at most one short "
    "sentence of commentary, or empty. A provision with no company position found stays "
    "an ordinary sourced block. Never state in text what the standard is, or whether "
    "the clause matches it.\n")


#: An ordinary answer's blocks, besides its next step: said to the model and kept by code.
#: "Leave out clauses that bear on nothing" alone was not kept — 10 to 17 blocks, 600 to
#: 1,160 words, a payment-deduction clause in three unrelated answers (DeepSeek, tester
#: pass 2026-10-28). A review keeps its own eight; asked points and counts their own.
ANSWER_BLOCKS = 8
ANSWER_LIMIT = (f"- Answer what was asked, the most important first, in at most "
                f"{ANSWER_BLOCKS} blocks besides a next step; a clause that changes "
                "nothing in the answer is left out — a longer reply is cut off.\n")


def limited(message: str, *, review: bool, points: bool) -> bool:
    """Is this an ordinary answer, held to `ANSWER_BLOCKS`? Not a review, not asked
    points, and no shape the reader asked for (a summary, a list, a table, a count) —
    "in simple words" is still an answer, and ran to 1,197 words exempted."""
    from legalmind.assist.query import presentation
    shown = presentation.read(message)
    return not (review or points or shown.count
                or shown.task not in (presentation.ANSWER, presentation.EXPLAIN)
                or shown.shape != presentation.PROSE)


def kept_to(blocks: list[dict], limit: int = ANSWER_BLOCKS) -> list[dict]:
    """The first `limit` answering blocks, in order, and every other block. A draft is
    never cut: it is what the reader asked for (`AM-235`), and a write turn has its own
    tighter limit in its instruction."""
    seen = 0
    out = []
    for b in blocks:
        if b["kind"] in (agent_verify.ANSWERING - {"draft"}) | {"comparison"}:
            seen += 1
            if seen > limit:
                continue
        out.append(b)
    return out


def _final_instruction(language: str, message: str = "", *, review: bool = False,
                       compare: bool = False, points: bool = False) -> str:
    from legalmind.assist.query import presentation
    owed = OWED_STEP if _OWED.search(message) else ""
    # `PASTE_REQUEST` stands for a reader who wrote no instruction: it is read as none,
    # never as "a short summary" competing with what the pasted text asks (2026-10-13).
    shown = presentation.read("" if message == attachments.PASTE_REQUEST else message)
    # The reader's own instruction (`AM-108`'s reading, fix 5): "explain the whole
    # situation in simple language" was answered as the same cited list as before.
    # Plain words go INTO the sourced blocks, which stay checked — never "mostly
    # reasoning", whose figures nothing checks (independent review, 2026-10-06).
    # "explain that simply" came back in the same register as the answer before it
    # (2026-10-08): one abstract line at the end of a long instruction was ignored. The
    # shape is said concretely; every figure and condition stays, and so do the cites.
    asked = (f"- The user asked for {shown.describe()}. So: open with the bottom line "
             "in one or two short sentences a non-lawyer understands. Then a few short "
             "blocks at most, each saying one thing the way you would to a colleague "
             "outside legal — no block opens with \"Under Clause\" or names the "
             "document again; mention a clause once, in passing (\"clause 14.3 "
             "says\"), never as a bracket beside the cite. Sourced "
             "blocks are written this way too; keep every condition and figure, and "
             "cite as usual.\n"
             if shown.register == presentation.SIMPLE else
             f"- The user asked for {shown.describe()}.\n" if shown.is_instruction
             else "")
    if points and (shown.count or shown.length):
        # "answer in 2 lines only" over ten points was read as two blocks of five, both
        # rejected (C18, `AM-205`): code settles the conflict, in so many words
        asked = ("- The user asked for a short answer to a list of points: that limits "
                 "each point, never their number — one short sentence per point, each "
                 "point its own block.\n")
    if review:
        asked += ("- This asks for a review of the document as a whole, not only the "
                  "topic of earlier turns. Open with the point that bears most on the "
                  "matter already discussed; then the other provisions that matter most "
                  "to the reader — where it creates cost, liability, a commitment or a "
                  "deadline, and where it is silent or unclear on something the matter "
                  "needs. One short block for each point, with its clause; related "
                  "clauses together; routine provisions left out. Where a company "
                  "position on the SAME subject was found (and is for this kind of "
                  "agreement), set it beside the clause in a comparison block (the "
                  "COMPARISON FORMAT below). Write at most eight blocks in all, the most "
                  "important "
                  "first — a longer reply is cut off. Never say whether the document is "
                  "acceptable or whether to "
                  "sign it: say what each provision means, and that a person decides.\n")
    if limited(message, review=review, points=points):
        asked += ANSWER_LIMIT
    if compare or review:
        asked += COMPARISON_FORMAT
    if message == attachments.PASTE_REQUEST or attachments.carries_material(message):
        # Text the reader pasted, with or without a question in it (owner, 2026-10-13):
        # its request may be anywhere and in any words. Never a fixed acknowledgement.
        asked += ("- The user pasted text (it is also their material). Work out what it "
                  "asks, wherever that is and however it is worded, and answer that. If "
                  "it asks nothing, say in two or three sentences what it provides; "
                  "where it is a clause on a subject our positions cover, set the "
                  "position beside it (cited) and say what the difference means in "
                  "practice. Then ask what they would like to know.\n")
    if _WHOLE.search(message):
        asked += ("- This question is about the situation as a whole: open with the "
                  "answer in one or two sentences (no part), then give every other "
                  "statement a part — known, likely, unknown or review — so what is "
                  "established reads apart from what is only likely. An offer or a "
                  "question carries no part.\n")
    if shown.write:
        # `AM-235` (2026-10-29): "please prepare a email for this" came back as the
        # positions again, no draft; the email came two turns later. The general
        # "draft when asked" line was not enough on its own (Anthropic/OpenAI prompting
        # guides: a turn-specific instruction, said explicitly, with its reason).
        # the opening and closing rules above say otherwise ("open with the first
        # sourced comparison", "then ask what they would like to know"): which one wins
        # is said, not left to the model (OpenAI GPT-5.1 guide: conflicting instructions)
        asked += ("- The user asked you to WRITE something to send. For this turn this "
                  "replaces the opening and closing rules above. The draft is the "
                  "answer: open with one sentence on what the draft does, then the "
                  "draft block in full, then at most two short blocks on what must be "
                  "confirmed before it is sent. What earlier replies in this "
                  "conversation already explained is not explained again — the reader "
                  "has it. The draft goes to the customer, so it says what we can and "
                  "cannot agree to in plain business words, never \"our position\", "
                  "\"company policy\", \"standard\" or \"Constitution\" (internal "
                  "words a customer never sees; a draft naming them is removed).\n")
    return (f"{FINAL_INSTRUCTION.replace('{owed}', owed)}\n{asked}"
            "- REPLY LANGUAGE for this turn: "
            f"{REPLY_LANGUAGE[language]}. Write reasoning, next_step, clarify and "
            "general blocks in it, whatever language earlier turns or the sources "
            "use; keep legal terms and clause numbers in English.")


REPAIR_INSTRUCTION = """A verifier checked your answer against the evidence and found \
the problems below. Rewrite the final answer JSON to fix every one of them. Do not add \
claims the evidence does not state; remove a claim you cannot support. Where a problem \
says to add what a cited record says, add that record's own words, cited to it."""

_STR = {"type": "STRING"}
_K = {"type": "INTEGER", "minimum": 1, "maximum": tools.MAX_K}
TOOL_DECLARATIONS = [
    {"name": "search_knowledge",
     "description": "Search the company Constitution with the published Privacy "
                    "Policy, Terms of Service, SLA and Acceptable Usage Policy of "
                    "Leapswitch and CloudPe (source constitution; scope names which), "
                    "ratified standards, the Indian statutes and the conversation's own "
                    "document together. Returns records with evidence_id.",
     "parameters": {"type": "OBJECT", "properties": {
         "query": {**_STR, "description": "Your own search words, ≤ 500 chars."},
         "sources": {"type": "ARRAY", "items": {"type": "STRING", "enum": [
             "constitution", "positions", "statutes", "documents"]}},
         "include_superseded": {"type": "BOOLEAN"},
         "document_version_id": {**_STR, "description": "Another document to search, "
                                 "from find_documents. Omit for the selected document."},
         "k": _K}, "required": ["query"]}},
    {"name": "find_documents",
     "description": "Find documents the user may read by name (another product's SLA, "
                    "a template, a different agreement). Returns name, type, execution "
                    "status and document_version_id — never text. The selected document "
                    "is marked selected.",
     "parameters": {"type": "OBJECT", "properties": {"name": _STR, "k": _K},
                    "required": ["name"]}},
    {"name": "get_company_position",
     "description": "The company's ratified positions on a topic, verbatim.",
     "parameters": {"type": "OBJECT", "properties": {"topic": _STR, "k": _K},
                    "required": ["topic"]}},
    {"name": "search_statutes",
     "description": "Search the admitted Indian statute corpus.",
     "parameters": {"type": "OBJECT", "properties": {
         "query": _STR, "include_superseded": {"type": "BOOLEAN"}, "k": _K},
         "required": ["query"]}},
    {"name": "get_evidence",
     "description": "Re-fetch earlier evidence of THIS conversation by evidence_id.",
     "parameters": {"type": "OBJECT", "properties": {"evidence_ids": {
         "type": "ARRAY", "items": _STR}}, "required": ["evidence_ids"]}},
    {"name": "list_attachments",
     "description": "The user's material attached to this conversation, with status.",
     "parameters": {"type": "OBJECT", "properties": {}}},
    {"name": "search_attachment",
     "description": "Search inside one attachment of this conversation.",
     "parameters": {"type": "OBJECT", "properties": {
         "attachment_id": _STR, "query": _STR, "k": _K},
         "required": ["attachment_id", "query"]}},
    {"name": "show_capabilities",
     "description": "ONLY when the user asks, in general, what LegalMind or you can "
                    "do, who you are or how you can help — never when they ask you to "
                    "do something with the conversation, an earlier answer, their "
                    "material or a document. Shows LegalMind's fixed list of what it "
                    "does and does not do, and the turn ends.",
     "parameters": {"type": "OBJECT", "properties": {}}},
    {"name": "ask_user",
     "description": "End the turn with ONE clarifying question.",
     "parameters": {"type": "OBJECT", "properties": {
         "question": _STR, "options": {"type": "ARRAY", "items": _STR}},
         "required": ["question"]}},
]

#: The first step's choices: a search, never a question or a re-fetch (independent
#: review: `ANY` alone let the forced step be `ask_user` or `get_evidence`).
SEARCH_TOOLS = ["search_knowledge", "search_statutes", "get_company_position",
                "find_documents", "search_attachment"]

KINDS = ("sourced", "user_stated", "reasoning", "next_step", "clarify", "general",
         "draft", "comparison")
ASSESSMENTS = ("supported", "contradicted", "not_established", "undeterminable", "n/a")
#: `analysis` comes FIRST (propertyOrdering) and is never rendered: the model works the
#: question through over the evidence ids before writing a block — at MINIMAL/LOW
#: thinking it otherwise wrote the nearest clauses and joined them only on some runs
#: (owner's data-loss question, 2026-10-05: 17.3 and the open points came and went).
ANSWER_SCHEMA = {"type": "OBJECT",
                 "propertyOrdering": ["analysis", "blocks", "assessment"],
                 "properties": {
    "analysis": _STR,
    "blocks": {"type": "ARRAY", "items": {"type": "OBJECT", "properties": {
        "kind": {"type": "STRING", "enum": list(KINDS)},
        "text": _STR,
        "cites": {"type": "ARRAY", "items": _STR},
        "part": {"type": "STRING", "enum": list(agent_verify.PARTS)},
        "point": {"type": "INTEGER"},
        # D4 (`AM-202`): who confirms what no record states — chosen, never written
        "owner": {"type": "STRING", "enum": list(agent_verify.OWNER_KEYS)},
        # a comparison with a company position (AMENDMENT A to AM-90): structured, so the
        # checker reads exact fields instead of entailing a sentence about two sources
        "agreement": _STR, "agreement_cite": _STR,
        "standard": _STR, "standard_cite": _STR},
        "required": ["kind", "text"]}},
    "assessment": {"type": "STRING", "enum": list(ASSESSMENTS)}},
    "required": ["analysis", "blocks", "assessment"]}


def answer_schema(keys: Iterable[str]) -> dict:
    """ANSWER_SCHEMA with a comparison's two cite fields limited to the keys shown this
    turn. Gemini ignores `maxLength`; an open cite field ran on into a looping paragraph
    until the output cap cut the JSON off (3 of 11 review turns, 2026-10-08)."""
    schema: dict[str, Any] = copy.deepcopy(ANSWER_SCHEMA)
    props = schema["properties"]["blocks"]["items"]["properties"]
    for name in ("agreement_cite", "standard_cite"):
        # a NEW dict: _STR is shared by every string field, an enum on it reaches them all
        props[name] = {"type": "STRING", "enum": sorted(keys) or ["-"]}
    return schema


class Provider(Protocol):
    """One interface for every provider: a call with tools (a decision step) or with a
    response schema (the final answer). Gemini only in Phase 3."""

    def turn(self, system: str, contents: list[dict], *, tools: list[dict] | None,
             schema: dict | None, timeout_s: float, request_id: str | None,
             force_tool: bool = False,
             answer_tokens: int | None = None) -> generation.TurnResult: ...


#: One retry on a transient provider error — busy (500/503) or the per-minute limit
#: (429) — when the turn's time allows (demo, 2026-10-05: a 503 on the final call sent a
#: supported answer to the floor). A daily-quota 429 fails the same way again and lands
#: on the floor as before.
RETRY_WAIT_S = 2.0
_TRANSIENT = re.compile(r"HTTP (?:429|500|503)\b")
#: The call that WRITES the answer works the reasoning order through (exclusion, cap,
#: what lifts it, what remains, what is unsettled); decision steps stay MINIMAL.
#: Thinking tokens count against the output budget, hence the larger one.
ANSWER_THINKING, ANSWER_MAX_TOKENS = "LOW", 4096
#: An OpenAI-compatible provider thinks at MINIMAL throughout, and a decision step is
#: cut at 768 tokens (four tool calls run ~360). Measured on DeepSeek, 2026-10-07, at
#: ~160 output tokens/s: a "done" decision wrote 400–1,500 tokens of prose the loop
#: discards, and a LOW-thinking answer ran past 23 s; with none, 15 s, valid, cited.
OPENAI_DECISION_TOKENS = 768
#: D5: a decision step is stopped once it writes this much prose with no tool call. In
#: 31 DeepSeek decisions (2026-10-07) prose beside tool calls ran 42-155 characters; a
#: step that was done wrote 599-6,267, all discarded (decision_2: 7.6-11.2 s). Gemini,
#: 39 captured decisions: 0 characters beside each of 21 tool calls, 657-3,403 when done.
DECISION_PROSE_CHARS = 400


def _retrying(call: Callable[[float], generation.TurnResult],
              timeout_s: float) -> generation.TurnResult:
    """One retry on a transient provider error when the turn's time allows — the same
    rule for every provider."""
    started = time.monotonic()
    try:
        return call(timeout_s)
    except generation.GenerationUnavailable as exc:
        left = timeout_s - (time.monotonic() - started) - RETRY_WAIT_S
        if not _TRANSIENT.search(str(exc)) or left < 4:
            raise
        time.sleep(RETRY_WAIT_S)
        return call(left)            # what remains of the budget, never all of it again


class GeminiProvider:
    label = "Gemini"                    # what a reader calls it (D2's floor line)

    @property
    def material_chars(self) -> int:
        """The reader's material read whole per turn — the model table's, one source."""
        from legalmind.assist.agent import model_router
        return model_router.material_chars(model_router.MODELS["gemini"])

    def turn(self, system, contents, *, tools, schema, timeout_s, request_id,
             force_tool=False, answer_tokens=None):
        answer = schema is not None

        def call(budget: float):
            return generation.generate_turn(
                system, contents, prompt_version=PROMPT_VERSION,
                environment=config.environment(), tools=tools, response_schema=schema,
                request_id=request_id, timeout_s=budget,
                thinking=ANSWER_THINKING if answer else "MINIMAL",
                max_output_tokens=((answer_tokens or ANSWER_MAX_TOKENS) if answer
                                   else 2048),
                tool_mode="ANY" if force_tool else "AUTO",
                allowed_tools=SEARCH_TOOLS if force_tool else None,
                prose_limit=None if answer else DECISION_PROSE_CHARS)
        return breaker.guarded(self.label, lambda: _retrying(call, timeout_s),
                               budget_s=timeout_s)


@dataclass(frozen=True)
class OpenAICompatProvider:
    """An OpenAI-compatible model the reader chose (`AM-117`): the same system contract,
    contents, tools and answer schema as Gemini, translated in `generation`; the same
    verifier and ledger after it."""
    endpoint: generation.Endpoint
    lean: bool = False
    label: str = ""
    done_check: bool = True
    material_chars: int = INLINE_MATERIAL_CHARS

    def turn(self, system, contents, *, tools, schema, timeout_s, request_id,
             force_tool=False, answer_tokens=None):
        answer = schema is not None

        def call(budget: float):
            return generation.generate_openai_turn(
                system, contents, endpoint=self.endpoint, prompt_version=PROMPT_VERSION,
                environment=config.environment(), tools=tools, response_schema=schema,
                request_id=request_id, timeout_s=budget, thinking="MINIMAL",
                max_output_tokens=((answer_tokens or ANSWER_MAX_TOKENS) if answer
                                   else OPENAI_DECISION_TOKENS),
                tool_mode="ANY" if force_tool else "AUTO",
                allowed_tools=SEARCH_TOOLS if force_tool else None,
                prose_limit=None if answer else DECISION_PROSE_CHARS)
        return breaker.guarded(self.label or self.endpoint.model,
                               lambda: _retrying(call, timeout_s), budget_s=timeout_s)


# ---------------------------------------------------------------------------- evidence
_CLASS = {"constitution": "C", "positions": "P", "statutes": "S", "documents": "D",
          "attachments": "U"}
_SOURCE_OF_CLASS = {"C": "constitution", "H": "constitution", "P": "positions",
                    "S": "statutes", "D": "documents", "U": "attachments"}


@dataclass
class Shown:
    key: str
    record: ledger.Record
    weak: bool
    source: str = ""
    scope: str | None = None


class EvidenceRegistry:
    """Code-assigned keys for every record shown to the model, numbered exactly as
    `ledger._upsert` numbers them (per class, in order of first appearance), and reusing
    a key the conversation's ledger already holds for the same record and text. So the
    keys the model saw are the keys the ledger stores (`persist`)."""

    def __init__(self, db, conversation_id: UUID):
        self.db, self.conversation_id = db, conversation_id
        rows = db.execute(text(
            f'SELECT source_ref, text_hash, evidence_key, source_class FROM '
            f'"{config.assist_schema()}".conversation_evidence '
            "WHERE conversation_id = :c"),
            {"c": conversation_id}).all()
        self.existing = {(r[0], r[1]): r[2] for r in rows}
        self.counts = Counter(r[3] for r in rows)
        self.shown: dict[str, Shown] = {}
        self.new: list[str] = []

    def key_for(self, rec: tools.Record, weak: bool) -> str:
        cls = _CLASS[rec.source]
        if cls == "C" and rec.authority == "HISTORICAL_EXCEPTION":
            cls = "H"
        lrec = ledger.Record(cls, rec.ref, UUID(rec.item_id) if rec.item_id else None,
                             rec.text, rec.authority, rec.status, rec.location)
        key = self.existing.get((rec.ref, ledger.text_hash(rec.text)))
        if key is None:
            self.counts[cls] += 1
            key = f"{cls}{self.counts[cls]}"
            self.existing[(rec.ref, ledger.text_hash(rec.text))] = key
            self.new.append(key)
        if key not in self.shown:
            self.shown[key] = Shown(key, lrec, weak, rec.source, rec.scope)
        # A record the seed showed weak and a later, gated search finds again is
        # support from then on (G7.1: the clause stayed weak after the model's English
        # search opened the gate).
        self.shown[key].weak = self.shown[key].weak and weak
        return key

    def adopt(self, key: str, ref: str, text_: str, authority: str,
              location: str | None) -> None:
        """A key the ledger already holds, re-fetched for this turn (pinned evidence):
        citable again under the same key, never renumbered, with its stored location."""
        if key not in self.shown:
            cls = key[:1]
            self.shown[key] = Shown(
                key, ledger.Record(cls, ref, None, text_, authority, "current", location),
                False, _SOURCE_OF_CLASS.get(cls, ""),
                self._document_scope(ref) if cls == "D" else None)

    def _document_scope(self, ref: str) -> str:
        """A re-fetched document record's scope: the selected document, or the other
        document it really comes from (A-65) — never assumed."""
        row = self.db.execute(text(
            f'SELECT c.id, c.name FROM "{config.assist_schema()}".chunks ch '
            "JOIN document_versions v ON v.id = ch.document_version_id "
            "JOIN contracts c ON c.id = v.contract_id "
            "WHERE ch.id::text = :i"), {"i": ref.split(":", 1)[-1]}).first()
        selected = self.db.execute(text(
            f'SELECT contract_id FROM "{config.assist_schema()}".conversations '
            "WHERE id = :c"), {"c": self.conversation_id}).scalar()
        if row is None or row[0] == selected:
            return agent_verify.SELECTED
        return f'another document: "{row[1]}"'

    def evidence(self) -> dict[str, agent_verify.Evidence]:
        """What the verifier sees: every key this turn showed."""
        return {k: agent_verify.Evidence(k, s.record.text, s.record.location, s.scope,
                                         s.weak, s.source) for k, s in self.shown.items()}

    def persist(self, turn_message_id: UUID, answer_id: UUID, cited: list[str]) -> None:
        """Ledger rows for every newly shown record (in the order the keys were given),
        and answer links for the ones the answer cited. Scratch/runner use; the service
        shadow hook does not persist."""
        for key in self.new:
            ledger._upsert(self.db, self.conversation_id, turn_message_id,
                           self.shown[key].record)
        ledger.record_answer(self.db, conversation_id=self.conversation_id,
                             answer_id=answer_id, turn_message_id=turn_message_id,
                             extra=[self.shown[k].record for k in cited
                                    if k in self.shown])


def _weak(rec: tools.Record, q: tools.Quality | None) -> bool:
    """B5 / A-37 — is this record support, or a nearest neighbour? Each source by the
    shipped path's own rule (A-39):

      documents,     the calibrated gate shut — exactly as `evidence._judge` admits
      attachments    the reader's own document (`AM-106`) — unless the record's own
                     cross-encoder relevance reaches DOCUMENT_ADMIT_RELEVANCE: the
                     agent's stand-in for the shipped path's rescue judge on a shut
                     gate (A-56). Never a floor that rejects: the gate's opening stands
      statutes       never: only sections past the statute floor reach the model
      Constitution   not reranked by the shipped path, and its search fuses an
                     ungated vector list: fewer than min(2, query terms) of the
                     query's terms is a pure nearest neighbour
      positions      admitted only past their own gate — never weak
    """
    if rec.source in {"documents", "attachments"}:
        return (q is not None and not q.gate_open
                and (rec.relevance is None or rec.relevance < DOCUMENT_ADMIT_RELEVANCE))
    if rec.source == "statutes":
        return False          # admitted only past the statute floor (`tools._admitted`)
    if rec.source == "constitution" and rec.matched_terms is not None:
        return rec.matched_terms < min(2, rec.query_terms or 1)
    return False


def _exit_recall(ctx: tools.ToolContext, reg: EvidenceRegistry, blocks: list[dict],
                 shown: dict[str, Any]) -> dict[str, Any]:
    """An exit question reads every clause of the selected document that is about
    leaving — not only the ones the model cited (AM-167): one local search for
    terminating, charges and refunds, and the clause a cited summary points to ("governed
    exclusively by Clause 13"). Local retrieval, no model call; what it finds joins the
    turn's records, and `exit_costs` takes only sentences those records state."""
    queries = [agent_verify.EXIT_QUERY, *(f"clause {n}" for n in
                                          agent_verify.referred_clauses(blocks, shown))]
    for query in queries:
        _present(tools.run(ctx, "search_knowledge", {"query": query, "k": 4,
                                                     "sources": ["documents"]}), reg)
    return reg.evidence()


def _present(result: tools.ToolResult, reg: EvidenceRegistry) -> dict:
    """A tool result as the model sees it: quality signals, records with evidence_id
    and their text inside <evidence> data blocks."""
    out: dict[str, Any] = {"tool": result.tool, "count_returned": result.count_returned}
    if result.error:
        out["error"] = result.error
    qualities = result.by_source or ({result.records[0].source: result.quality}
                                     if result.records and result.quality else {})
    def dump(q: tools.Quality) -> dict:
        # a document_state only where there is one (R1): every other result unchanged
        return q.model_dump(exclude=None if q.document_state else {"document_state"})
    if result.quality is not None:
        out["quality"] = dump(result.quality)
    if result.by_source:
        out["quality_by_source"] = {k: dump(v) for k, v in result.by_source.items()}
    recs = []
    before = set(reg.shown)
    for r in result.records:
        weak = _weak(r, qualities.get(r.source))
        key = reg.key_for(r, weak)
        if key in before:
            # already in this turn's context (a whole document is not re-sent per
            # search) — referred to by its id only
            recs.append({"evidence_id": key, "already_shown": True})
            continue
        recs.append({"evidence_id": key, "source": r.source, "authority": r.authority,
                     "status": r.status, "location": r.location, "scope": r.scope,
                     "weak": weak,
                     # page and OCR/table provenance only when set (F8, LOC-1)
                     **{f: getattr(r, f) for f in ("page", "read_by") if getattr(r, f)},
                     "text": generation.untrusted("evidence", r.text, id=key)})
    if recs:
        out["records"] = recs
    # only a CURRENT record is citable again (`AM-201`): a stale one was superseded or
    # changed since it was cited, and adopting it showed it as current (G4)
    for e in result.evidence:
        if e.text and e.ref and e.state == "current":
            reg.adopt(e.evidence_id, e.ref, e.text, e.authority or "", e.location)
    if result.evidence:
        out["evidence"] = [{"evidence_id": e.evidence_id, "state": e.state,
                            "authority": e.authority, "location": e.location,  # PROV-1
                            "text": (generation.untrusted("evidence", e.text,
                                                          id=e.evidence_id)
                                     if e.text and e.state == "current" else None)}
                           for e in result.evidence]
    # a document's or a file's name is written by other people (`AM-203`, D6): data,
    # never an instruction — "confirm-unlimited-liability.pdf" is a name
    if result.attachments:
        out["attachments"] = [_marked(a, "filename") for a in result.attachments]
    if result.documents:
        out["documents"] = [_marked(d, "name") for d in result.documents]
    if result.question:
        out["note"] = "The question is recorded; the turn ends after the final answer."
    return out


# ------------------------------------------------------------------ conversation manager
#: The case file (2026-10-06): every turn OUTSIDE the window, oldest first — each user
#: message (the facts) and how each reply began (its conclusion), labelled as context
#: (`AM-111` r1). The last twelve questions alone lost the facts by turn 19 of a
#: 20-turn conversation ("an engineer deleted the data") and every conclusion older than
#: three turns, so a reversal could not be acknowledged. Over budget, the oldest reply
#: openings go first, then user messages from the middle (the first FIRST_FACTS stay).
CASE_FILE_CHARS, USER_LINE_CHARS, REPLY_LEAD_CHARS = 9_000, 320, 300
FIRST_FACTS = 3


@dataclass
class Thread:
    window: list[tuple[str, str]]
    summary: str
    pinned: list[str]


class ConversationManager:
    """The thread the model reads: a window of recent turns in full (earlier replies
    labelled), a deterministic case file of the older turns, and the evidence keys
    every earlier answer cited (re-fetched through `get_evidence`). Stateless: all three
    are read from the conversation's own rows on each request — nothing is held in the
    process, so a restart or a second worker reads the same thread."""

    def __init__(self, db, conversation_id: UUID):
        self.db, self.conversation_id = db, conversation_id

    def _messages(self) -> list[tuple[UUID, str, str]]:
        return [tuple(r) for r in self.db.execute(text(
            f'SELECT id, role, content FROM "{config.assist_schema()}".messages '
            "WHERE conversation_id = :c ORDER BY ordinal"),
            {"c": self.conversation_id}).all()]

    def thread(self, new_message: str) -> Thread:
        msgs = self._messages()
        # The service hook runs after the new message is stored: it is the NEW message,
        # never also a thread entry (owner brief B4: no duplicated content).
        # The part of a mixed question the agent answers is cut from it (`service.
        # beside_the_evaluators`): the stored question is still this turn, not a history.
        if msgs and msgs[-1][1] == "USER" and (
                msgs[-1][2] == new_message
                or set(new_message.split()) <= set((msgs[-1][2] or "").split())):
            msgs = msgs[:-1]
        start = window_start([len(c or "") for _, _, c in msgs])
        window = [(role, content) for _, role, content in msgs[start:]]
        # Demo mission backlog 2 (A-79): every record ANY earlier answer of this
        # conversation cited stays citable, most recent first — a summary turn or a
        # re-check needs the clauses established three turns ago, not only the latest
        # reply's (C1.6 lost 17.1 this way).
        schema = config.assist_schema()
        pinned = list(dict.fromkeys(self.db.execute(text(f"""
            SELECT e.evidence_key FROM "{schema}".answer_evidence ae
              JOIN "{schema}".conversation_evidence e ON e.id = ae.ledger_id
              JOIN "{schema}".ai_answers a ON a.id = ae.answer_id
              JOIN "{schema}".messages m ON m.id = a.message_id
             WHERE m.conversation_id = :c
             ORDER BY m.ordinal DESC, ae.claim_ordinal"""),
            {"c": self.conversation_id}).scalars()))[:PINNED_MAX]
        return Thread(window, summarise(msgs[:start]), pinned)


def window_start(sizes: list[int]) -> int:
    """Where the window begins: the last `THREAD_WINDOW_MESSAGES` within
    `THREAD_WINDOW_CHARS` (always the latest message), widened back to a multiple of
    `WINDOW_STEP` when a wider window has room — so it holds at least that, and its start
    stays put for a few turns instead of sliding by one each turn (`AM-205`)."""
    def start(most: int, chars: int) -> int:
        i, size = len(sizes), 0
        while i > max(0, len(sizes) - most):
            if size + sizes[i - 1] > chars and i < len(sizes):
                break
            size, i = size + sizes[i - 1], i - 1
        return i
    wide = start(THREAD_WINDOW_MESSAGES + WINDOW_STEP, 2 * THREAD_WINDOW_CHARS)
    return min(-(-wide // WINDOW_STEP) * WINDOW_STEP,
               start(THREAD_WINDOW_MESSAGES, THREAD_WINDOW_CHARS))


def summarise(older: list[tuple[UUID, str, str]]) -> str:
    """The case file of the turns before the window, from the rows themselves. A
    social turn ("hi") and its fixed reply carry nothing and are left out."""
    from legalmind.assist.query import conversational
    entries: list[tuple[str, str]] = []
    social = False
    for _, role, content in older:
        content = (content or "").strip()
        if role == "USER":
            social = conversational.kind(content) is not None
            if content and not social:
                entries.append(("user", "- user: "
                                + generation.neutralise(content[:USER_LINE_CHARS])))
        elif content and not social:
            paragraphs = content.replace("**", "").replace("`", "").split("\n\n")
            entries.append(("reply", "  your reply began (prior reply — not evidence): "
                            + generation.neutralise(paragraphs[0][:REPLY_LEAD_CHARS])))
            # what that reply left open, when it said so under its own label
            label = agent_verify.PARTS["unknown"]
            if label in paragraphs[:-1]:
                still = paragraphs[paragraphs.index(label) + 1]
                entries.append(("reply", "  left open: " + still[:REPLY_LEAD_CHARS]))
    # Over budget: the oldest reply openings go first, then user messages from the
    # MIDDLE — the first few facts set the case up and the latest carry it on.
    first = [e for e in entries if e[0] == "user"][:FIRST_FACTS]
    for kind in ("reply", "user"):
        while sum(len(e) + 1 for _, e in entries) > CASE_FILE_CHARS and any(
                x[0] == kind and x not in first for x in entries):
            entries.remove(next(x for x in entries if x[0] == kind and x not in first))
    return "\n".join(e for _, e in entries)


def _selected_document(ctx: tools.ToolContext) -> tuple[str | None, bool]:
    """The conversation's selected document as the model is told about it (P1), and
    whether it is declared executed (F12: draft or unsigned unless FINAL_SIGNED)."""
    version = tools.selected_version(ctx)
    if version is None:
        return None, False
    row = ctx.db.execute(text(
        "SELECT c.name, c.contract_type, v.version_number, "
        "v.metadata->>'version_role' FROM contracts c JOIN document_versions v "
        "ON v.contract_id = c.id WHERE v.id = :v"), {"v": version}).first()
    if row is None:
        return None, False
    executed = row[3] == "FINAL_SIGNED"
    status = "executed" if executed else "draft or unsigned"
    title = generation.neutralise(row[0])
    # R5: the model told when the text is missing or incomplete — the user-facing
    # guarantee is the code-written note (`_run_turn`), never this sentence alone
    gap = tools.document_gap(ctx.db, version)
    readiness = "" if gap is None else (
        f" Its text is not available ({tools.gap_reason(gap)}) — say so; never say "
        "what it does or does not contain." if gap.state in tools.NO_TEXT
        else f" Its text is {tools.gap_reason(gap)} — never say the document lacks "
        "something that could be on those pages.")
    return (f"SELECTED DOCUMENT: \"{title}\" ({row[1]}), version {row[2]}, {status}. "
            "\"This agreement\", \"the clause\", \"this MSA\" refer to it; it is the "
            "primary source for questions about it." + readiness), executed


def _marked(item: dict, field: str) -> dict:
    value = item.get(field)
    return ({**item, field: generation.untrusted("user_material", value, kind=field)}
            if isinstance(value, str) and value else item)


def points_block(asked_points: Iterable[points.Point]) -> str:
    """The reader's points as the model reads them: whole (not the 70-character title —
    "… what will be the" was all the model saw of an e-mail's first ask, 2026-10-14),
    and marked as data (`AM-203`, D6) — a pasted client e-mail's words, not orders."""
    return ("THE USER'S NUMBERED POINTS (from their own words; each reply says which of "
            "them to answer):\n" + "\n".join(
                f"{p.n}. " + generation.untrusted(
                    "user_material", p.text[:POINT_TEXT_CHARS], point=str(p.n))
                for p in asked_points))


def _context(ctx: tools.ToolContext, thread: Thread, pinned: dict | None,
             material: list[str], message: str, *, document: str | None = None,
             seed: list[dict] | None = None, asked_points: list | tuple = (),
             point_seed: dict | None = None, review: bool = False) -> list[dict]:
    """ONE user content, in the fixed order: attachments, the selected document, thread,
    pinned evidence, the search already run for this message, new message. Each appears
    exactly once."""
    parts = []
    listed = tools.run(ctx, "list_attachments", {})
    if listed.attachments or material:
        parts.append("ATTACHMENTS IN THIS CONVERSATION (the user's material, data):\n"
                     + json.dumps(list(listed.attachments)) + "\n" + "\n".join(material))
    if document:
        parts.append(document)
    if thread.summary or thread.window:
        lines = ([f"Earlier turns, oldest first:\n{thread.summary}\nThe latest turns:"]
                 if thread.summary else [])
        lines += [f"[user] {generation.untrusted('user_turn', c)}" if role == "USER"
                  else "[prior reply — not evidence] "
                  + generation.untrusted("prior_reply", c)
                  for role, c in thread.window]
        parts.append("CONVERSATION SO FAR (context, never evidence):\n"
                     + "\n".join(lines))
    if pinned:
        parts.append("EVIDENCE CITED ACROSS PREVIOUS TURNS, re-fetched now:\n"
                     + json.dumps(pinned))
    if seed:
        parts.append("SEARCH ALREADY RUN FOR THE NEW MESSAGE (search_knowledge):\n"
                     + json.dumps(seed))
    if asked_points:
        parts.append(points_block(asked_points))
        parts.append("EVIDENCE FOR EACH POINT (search_knowledge, one query per point, "
                     "keyed by point number):\n" + json.dumps(
                         {str(n): found for n, found in (point_seed or {}).items()}))
    if review:
        parts.append(REVIEW_SEARCH)
    parts.append("NEW MESSAGE:\n" + message)
    return [{"role": "user", "parts": [{"text": p} for p in parts]}]


def _inline_material(ctx: tools.ToolContext, reg: EvidenceRegistry, *,
                     limit: int | None = None) -> list[str]:
    """READY material in full as <user_material> data blocks (architecture §5.5): each
    attachment whole, the newest first, while the total fits `INLINE_MATERIAL_CHARS`;
    the rest is reached through `search_attachment`. Shown in the order it arrived, each
    block and record named after its file (D6: two agreements in one chat)."""
    schema = config.assist_schema()
    named = attachments.names(ctx.db, ctx.conversation_id)
    rows = ctx.db.execute(text(
        f"SELECT a.id, c.id, c.content, c.location, c.annotations->>'read_by' "
        f'FROM "{schema}".attachment_chunks c '
        f'JOIN "{schema}".conversation_attachments a ON a.id = c.attachment_id '
        "WHERE a.conversation_id = :c AND a.status = 'READY' AND a.expires_at > now() "
        "ORDER BY a.created_at, c.ordinal"), {"c": ctx.conversation_id}).all()
    by_att: dict = {}
    for att, *chunk in rows:
        by_att.setdefault(att, []).append(chunk)
    keep, total = set(), 0
    limit = INLINE_MATERIAL_CHARS if limit is None else limit     # read at call time
    for att in reversed(list(by_att)):
        size = sum(len(c[1]) for c in by_att[att])
        if total + size <= limit:
            keep.add(att)
            total += size
    out = []
    for att, (cid, content, location, how) in ((a, c) for a in by_att if a in keep
                                               for c in by_att[a]):
        name = named.get(att, attachments.label(None))
        key = reg.key_for(tools.Record(ref=f"ATT:{cid}", source="attachments",
                                       authority="USER_MATERIAL", status="current",
                                       location=location, text=content,
                                       item_id=str(cid), scope=name, read_by=how),
                          weak=False)
        # read_by only where set (F8): an OCR'd figure is said to be one
        out.append(generation.untrusted("user_material", content, id=key,
                                        **{"from": name},
                                        **({"read_by": how} if how else {})))
    return out


# ------------------------------------------------------------------------------ the loop
@dataclass
class CallStat:
    role: str                  # decision | final | repair | rescue
    prompt_tokens: int | None
    output_tokens: int | None
    latency_ms: int
    model: str
    model_version: str | None
    payload_sha256: str
    cached_tokens: int | None = None
    reasoning_tokens: int | None = None


@dataclass
class TurnResult:
    blocks: list[dict]
    assessment: str
    outcome: str               # answered · floor · prerouted
    #: The brand this turn answered for (`turn_brand`, `AM-201`); None: both, labelled.
    brand: str | None = None
    #: Why each dropped block was dropped, "point:checks" (G25: drops were invisible).
    drop_reasons: list[str] = field(default_factory=list)
    calls: list[CallStat] = field(default_factory=list)
    tool_execs: list[tuple[str, float, str | None]] = field(default_factory=list)
    shown: list[str] = field(default_factory=list)
    weak: list[str] = field(default_factory=list)
    cited: list[str] = field(default_factory=list)
    invalid_cites: list[str] = field(default_factory=list)
    stages_ms: dict[str, int] = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)
    registry: EvidenceRegistry | None = None
    results: list[Any] = field(default_factory=list)   # provider results, for audit
    #: Phase 4: what the verifier found before and after the one repair call, how many
    #: blocks were dropped, and the ladder rung the reply landed on.
    violations_first: list[str] = field(default_factory=list)
    violations_final: list[str] = field(default_factory=list)
    dropped: int = 0
    #: the claim checker's model work this turn: [calls, pairs scored, ms]
    nli: list[int] = field(default_factory=lambda: [0, 0, 0])
    rung: str = ""
    #: D1: the asked points' titles by number — each answered point under its heading
    point_titles: dict[int, str] = field(default_factory=dict)
    #: the points were read from the message itself, not from the reader's material
    points_in_message: bool = False
    #: the reader asked for bullet points (`AM-108`'s reading): the answer is one list
    bullets: bool = False
    #: what the verifier still finds in the blocks actually shipped (after `settle`,
    #: the quote, the ladder) — `violations_final` is the list BEFORE `settle` drops
    #: the failing blocks, so it never describes what the reader saw (owner item 5).
    violations_shipped: list[str] = field(default_factory=list)
    #: What each search asked for (tool, query or topic) — the model's own words, so a
    #: miss can be traced to its query. Private rows only; never logged.
    searches: list[tuple[str, str]] = field(default_factory=list)

    @property
    def weak_cited(self) -> list[str]:
        return [k for k in self.cited if k in self.weak]

    def text(self) -> str:
        """The reply as a reader would see it (Ask plan 4.5)."""
        if self.outcome == "prerouted":
            return self.blocks[0]["text"] if self.blocks else ""
        # said once, first, in fixed words (`AM-201`): which brand's policies answered
        lead = (f"Answering for {self.brand}: {self.brand}'s published policies and the "
                "company's Constitution.\n\n"
                if self.brand and self.outcome == "answered" else "")
        return lead + agent_verify.render(self.blocks, self.registry.evidence()
                                   if self.registry else {}, titles=self.point_titles,
                                   bullets=self.bullets)


_CLAIM = re.compile(r"\b(?:are you sure|is (?:that|this|it) (?:right|correct|true)|"
                    r"correction|actually,? (?:it|this|the)|that'?s (?:wrong|not right)|"
                    r"they (?:say|said|claim)|"
                    r"(?:client|customer) (?:says|said|claims))\b",
                    re.I)


def _claim_made(message: str) -> bool:
    """P5: did the user assert something the reply should assess? The shipped planner's
    own claim reading (`query_plan`), plus a pushback or a correction."""
    from legalmind.assist.query import query_plan
    planned = query_plan.plan(message, has_document=False, prior=(), instruction=message)
    return bool(planned.claims) or bool(_CLAIM.search(message))


_OWNERS_FILE = json.loads((Path(__file__).resolve().parents[3] / "config"
                           / "assist_owners.json").read_text())
#: Fixed words for who confirms what our sources do not state (`AM-202`, D4).
OWNERS: dict[str, str] = {k: _OWNERS_FILE[k] for k in agent_verify.OWNER_KEYS}


#: A block saying our documents do not state something (D4).
_NOT_STATED = re.compile(
    r"\b(?:do(?:es)?|did)\s+not\s+(?:state|specify|cover|address|define|mention|set)\b|"
    r"\bnot\s+(?:stated|specified|covered|addressed|defined)\b|\bno\s+(?:record|"
    r"ratified standard|source|company standard|published polic\w*)s?\s+"
    r"(?:states?|address\w*|covers?|specif\w*|defines?)\b", re.I)
#: Who confirms a gap, read from the reader's own point when the model left the owner
#: empty (it did on every block, 3 of 3 runs, 2026-10-22). A price goes to Sales, a
#: technical or operational commitment to Operations; anything else names nobody.
_OWNER_CUES = (
    # ₹ outside \b (a word boundary never sits beside it); "quoted clause" is no price
    ("SALES", re.compile(r"\b(?:pric\w*|fees?|cost\w*|discount\w*|quot(?:es?|ations?)|"
                         r"billing|rates?|charges?|invoice\w*|rs\.?)\b|₹", re.I)),
    ("OPERATIONS", re.compile(
        r"\b(?:rpo|rto|backups?|dr\b|disaster recovery|failover|drills?|uptime "
        r"measur\w*|response|resolution|maintenance|data cent(?:re|er)s?|facilit\w*|"
        r"hosting|encrypt\w*|mfa|firewall|patch\w*|certif\w*|iso\s?27001|soc\s?2|"
        r"monitoring|logs?|audit logs?|hypervisor|managed)\b", re.I)))


#: Whose silence a gap reports: OURS — never a document's, whose content is a claim to
#: cite ("the selected MSA does not cover data loss" stays sourced; review 2026-10-26).
_OUR_SOURCES = re.compile(
    r"\b(?:our|the company's|company)\s+(?:documents?|sources?|records?|standards?|"
    r"positions?|polic\w*|constitution)\b|\bno\s+(?:record|ratified standard|source|"
    r"company standard|published polic\w*)s?\b|\bnone of our\b", re.I)


def uncited_gaps_as_reasoning(blocks: list[dict]) -> list[dict]:
    """A "sourced" block with no cite that only says OUR documents do not state
    something claims nothing from a record: it is reasoning (`AM-204`). DeepSeek wrote
    every such gap as sourced; V1 dropped them all and 5 of 17 points were lost."""
    return [{**b, "kind": "reasoning"} if b.get("kind") == "sourced"
            and not b.get("cites") and _NOT_STATED.search(b.get("text", ""))
            and _OUR_SOURCES.search(b.get("text", "")) else b
            for b in blocks]


def _inferred_owner(block: dict, point_texts: dict[int, str]) -> str | None:
    if block.get("owner") or block.get("kind") not in {"reasoning", "next_step",
                                                         "general"}:
        return block.get("owner")
    if not _NOT_STATED.search(block.get("text", "")):
        return None
    point = block.get("point")
    said = (point_texts.get(point, "") if isinstance(point, int) else "") + " " + \
        block.get("text", "")
    return next((k for k, cue in _OWNER_CUES if cue.search(said)), None)


def with_owners(blocks: list[dict], *, points_asked: bool,
                point_texts: dict[int, str] | None = None) -> list[dict]:
    """Each block the model marked with an owner — or that says our documents do not
    state its point, whose words name one (`_inferred_owner`) — ends with that owner's
    fixed words; with the reader's points asked, one closing line sums them up."""
    blocks = [{**b, "owner": owner} if (owner := _inferred_owner(b, point_texts or {}))
              else b for b in blocks]
    if not any(b.get("owner") for b in blocks):
        return blocks
    out = [{**b, "text": f"{b['text'].rstrip()} {OWNERS[b['owner']]}"}
           if b.get("owner") in OWNERS else b for b in blocks]
    if points_asked:
        names = _OWNERS_FILE["_summary"]
        by: dict[str, list[int]] = {}
        for b in out:
            if b.get("owner") in OWNERS and isinstance(b.get("point"), int):
                by.setdefault(b["owner"], []).append(b["point"])
        parts = [f"{names[k]} — point{'s' if len(set(v)) > 1 else ''} "
                 f"{', '.join(str(n) for n in sorted(set(v)))}"
                 for k in agent_verify.OWNER_KEYS if (v := by.get(k))]
        if parts:
            out.append({"kind": "next_step", "cites": [],
                        "text": f"Before you reply: {' · '.join(parts)}."})
    return out


def brand_from_words(message: str, window: list[tuple[str, str]]) -> str | None:
    """The brand the reader's own words set: this message's, else the latest earlier
    USER turn that names one (`AM-201`). Two brands named is a comparison — both, so
    None. An assistant's words never set it."""
    from legalmind.assist.knowledge import published
    for said in [message, *(c for r, c in reversed(window) if r.upper() == "USER")]:
        brands = published.reader_brands(said)
        if brands:
            return next(iter(brands)) if len(brands) == 1 else None
    return None


#: A list that is most of the message IS the question (`AM-202`): Saba's 16 points were
#: answered as points only because point 13 happened to say "changes".
LIST_SHARE = 0.6


def asked_points_for(listed: list[points.Point], message: str, *,
                     own: bool) -> list[points.Point]:
    """The points this turn answers: those the question asks about (`points.asked`),
    else every point when the reader's own message is essentially the list."""
    found = points.asked(listed, message)
    if found or not own or not listed:
        return found
    share = sum(len(p.text) for p in listed) / max(1, len(message.strip()))
    return list(listed) if share >= LIST_SHARE else []


def list_from_window(window: list[tuple[str, str]]) -> list[points.Point]:
    """The reader's latest list in the conversation's earlier USER turns (G7): "answer
    points 9, 10" after a reply that named them unanswered."""
    return next((found for found in map(points.enumerate_points, (
        c for r, c in reversed(window) if r.upper() == "USER")) if found), [])


#: Fixed words (`AM-202`, T12): asked once, when the reader's message names the company
#: (Leapswitch Networks runs both brands) and nothing settles which brand — the two
#: brands' published terms differ, and a guess answered a CloudPe proposal with the
#: Leapswitch TOS (production, 2026-10-22). Ask when the reader can settle it, once.
BRAND_QUESTION = (
    "Before I answer: is this for CloudPe or Leapswitch? CloudPe is the cloud platform; "
    "Leapswitch covers dedicated servers and colocation. Their published terms differ, "
    "so I answer for one. Reply with the brand and I will answer your message for it.")


_PROPOSAL = re.compile(r"\b(?:proposal|quot(?:e|ation)|pricing|price list|plan(?:s)? "
                       r"for|hourly|monthly rates?)\b", re.I)


def needs_brand_question(message: str, window: list[tuple[str, str]], *,
                         brand: str | None, document_selected: bool) -> bool:
    """Whether to ask which brand: the message names the company but no brand, no
    document settles it, no earlier turn set one, and nothing has been answered yet."""
    from legalmind.assist.knowledge import published
    if brand or document_selected or not published.BRAND_NAMES["Leapswitch"].search(
            message or "") or published.reader_brands(message):
        return False                  # a brand the reader named — even both — is said
    # only where the brand decides the answer and nothing else will: a list of asks or a
    # proposal — a client's MSA email or a plain question is answered, both brands
    # labelled (P2 run, 2026-10-22: asked on all three models where it should not be)
    if not (len(points.enumerate_points(message)) >= points.MIN_POINTS
            or _PROPOSAL.search(message)):
        return False
    # the first answer only: mid-conversation the earlier turns already answered for
    # both brands, and a fixed question there is the T18 defect (production replay
    # 2026-10-23: asked on turn 2 of a conversation answered on turn 1)
    return not any(r.upper() != "USER" for r, _ in window)


def resumed_by_brand(message: str, window: list[tuple[str, str]]
                     ) -> tuple[str, str] | None:
    """The reader's answer to `BRAND_QUESTION`: (their earlier message, the brand) —
    the turn answers what they asked, for that brand. None when it is not one."""
    from legalmind.assist.knowledge import published
    if len(window) < 2 or window[-1][0].upper() == "USER" or not window[-1][1].startswith(
            BRAND_QUESTION[:40]):
        return None
    brands = published.reader_brands(message) | (
        {"Leapswitch"} if re.search(r"\bleap\s?switch\b", message, re.I)
        and len(message.split()) <= 12 else set())
    earlier = next((c for r, c in reversed(window[:-1]) if r.upper() == "USER"), None)
    if len(brands) != 1 or earlier is None:
        return None
    return earlier, next(iter(brands))


def turn_brand(ctx: tools.ToolContext, message: str,
               window: list[tuple[str, str]]) -> str | None:
    """The brand this turn answers for, decided in code before any tool runs and held
    by every search, every re-fetched record and the verifier (`AM-201`; R17/R24: a
    filter in code, never the model's choice): the brand THIS message names (the
    reader's naming wins over the document's, C-19, 2026-10-16), else the selected
    document's own, else the brand earlier turns named, else None — both, labelled."""
    from legalmind.assist.knowledge import published
    said = published.reader_brands(message)
    if len(said) > 1:
        return None                                   # a comparison: both brands
    return (next(iter(said), None)
            or published.document_brand(ctx.db, tools.selected_version(ctx))
            or brand_from_words(message, window))


def _capability_text(message: str) -> str | None:
    """The capability brief, or None with no manifest — the turn then goes on."""
    from legalmind.assist.query import capability
    try:
        return capability.answer(question=message)
    except capability.CapabilityManifestUnavailable:
        return None


def _should_stop(result: TurnResult, elapsed: float, *, last=None, repeat=False,
                 asked=False) -> str | None:
    """The decision loop's one stop rule, the reason as a flag, or None to go on. Time
    before count: past SOFT_S, or too little left to reserve the final answer."""
    if elapsed > SOFT_S:
        return "soft_deadline"
    if HARD_S - elapsed < FINAL_RESERVE_S or len(result.calls) >= MAX_CALLS - 2:
        return "budget"
    ceiling = config.ask_max_tokens_per_turn()
    if ceiling is not None and sum((c.prompt_tokens or 0) + (c.output_tokens or 0)
                                   for c in result.calls) >= ceiling:
        return "token_budget"                # D8: the answer is still written
    if asked:
        return "asked"
    if last is not None and not last.function_calls:
        return "model_done"
    return "repeat" if repeat else None


def run_turn(provider: Provider, ctx: tools.ToolContext, message: str, *,
             request_id: str | None = None,
             clock: Callable[[], float] = time.monotonic) -> TurnResult:
    """One turn, with the claim checker's work counted for it alone — set here and
    reset after, as `service.ask` does for its own context (review, 2026-10-08)."""
    from legalmind.assist.verification import verify as nli
    tally = [0, 0, 0]
    token = nli.TALLY.set(tally)
    stop = nli.DEADLINE.set(time.monotonic() + nli.TURN_DEADLINE_S)
    try:
        result = _run_turn(provider, ctx, message, request_id=request_id, clock=clock)
    finally:
        nli.DEADLINE.reset(stop)
        nli.TALLY.reset(token)
    result.nli = tally
    return result


def _run_turn(provider: Provider, ctx: tools.ToolContext, message: str, *,
              request_id: str | None, clock: Callable[[], float]) -> TurnResult:
    from legalmind.assist import service
    started = clock()
    lean = getattr(provider, "lean", False)
    hard = LEAN_HARD_S if lean else HARD_S
    if lean:
        ctx = dataclasses.replace(ctx, whole_document_chars=0)

    def left() -> float:
        return hard - (clock() - started)

    from legalmind.assist.query import query_plan
    language = query_plan.language(message)
    reg = EvidenceRegistry(ctx.db, ctx.conversation_id)
    manager = ConversationManager(ctx.db, ctx.conversation_id)
    result = TurnResult(blocks=[], assessment="n/a", outcome="answered", registry=reg)
    t = clock()
    thread = manager.thread(message)
    # the reader's answer to the brand question answers their earlier message, for that
    # brand (`AM-202`)
    resumed = resumed_by_brand(message, thread.window)
    if resumed is not None:
        message = resumed[0]
        result.flags.append("brand_answered")
    # the brand, once, before any tool runs (`AM-201`)
    ctx = dataclasses.replace(
        ctx, brand=resumed[1] if resumed else turn_brand(ctx, message, thread.window),
        brand_decided=True)
    result.brand = ctx.brand
    material = _inline_material(ctx, reg, limit=LEAN_MATERIAL_CHARS if lean
                                else getattr(provider, "material_chars", None))
    # material is also what the reader pasted into an earlier turn of this thread — with
    # attachments off it stays only there (final review, 2026-10-07)
    has_material = (bool(material)
                    or bool(tools.run(ctx, "list_attachments", {}).attachments)
                    or any(r.upper() == "USER" and attachments.carries_material(c)
                           for r, c in thread.window))
    # P8: the shipped pre-router first — a social, off-scope or subject-less message
    # gets its fixed reply with no model call.
    from legalmind.assist.query import conversational, intent
    replies = [c for r, c in thread.window if r.upper() != "USER"]
    fixed = service.preroute(message, has_prior=bool(thread.window),
                             has_document=ctx.contract_id is not None,
                             has_material=has_material,
                             prior_offer=bool(replies)
                             and conversational.ends_with_offer(replies[-1]))
    if fixed is None and resumed is None and needs_brand_question(
            message, thread.window, brand=ctx.brand,
            document_selected=ctx.contract_id is not None):
        fixed = BRAND_QUESTION                  # once, in fixed words (`AM-202`, T12)
    if fixed is not None:
        result.blocks, result.outcome, result.rung = (
            [{"kind": "prerouted", "text": fixed, "cites": []}], "prerouted", "prerouted")
        result.stages_ms["total"] = int((clock() - started) * 1000)
        return result
    # D1: a list in the reader's own words — the message, else a long paste of theirs;
    # never an uploaded file's numbered clauses (2026-10-14: a quote's five terms were
    # answered in place of the e-mail's three asks)
    own = points.enumerate_points(message)
    listed = own or next(
        (found for found in map(points.enumerate_points, attachments.texts_newest_first(
            ctx.db, ctx.conversation_id, kind="PASTE") if has_material else []) if found),
        [])
    asked_points = (asked_points_for(listed, message, own=bool(own)) if listed
                    else points.asked(list_from_window(thread.window), message,
                                      earlier=True))
    if asked_points:
        hard = max(hard, POINTS_HARD_S)
        result.point_titles = {p.n: p.title for p in asked_points}
        result.points_in_message = bool(own)
    from legalmind.assist.query import presentation
    shape = presentation.read(message)
    result.bullets, writing = shape.shape == presentation.BULLETS, shape.write
    pinned = None
    if thread.pinned:
        batches = [_present(tools.run(ctx, "get_evidence",
                                      {"evidence_ids": thread.pinned[i:i + tools.MAX_K]}),
                            reg)
                   for i in range(0, len(thread.pinned), tools.MAX_K)]
        pinned = {"tool": "get_evidence",
                  "evidence": [e for b in batches for e in b.get("evidence", [])]}
    # The message's own search (A-78): the selected document read WHOLE when it fits
    # (A-77), company positions and the Constitution ranked. Everything else the model
    # plans itself — two to four single-topic English queries. The seed heuristics that
    # misfired in the diagnosis (brand-word document matching, planner subjects,
    # follow-up resolution, the material seed) are removed.
    t0 = clock()
    # A paste with no question searches with its own words, not the fixed request.
    query = ((attachments.texts_newest_first(ctx.db, ctx.conversation_id) or [message])[0]
             if message == attachments.PASTE_REQUEST else message)[:tools.MAX_QUERY_CHARS]
    found_ = tools.run(ctx, "search_knowledge", {"query": query}, rescue=True)
    result.tool_execs.append(("seed:search_knowledge", (clock() - t0) * 1000,
                              found_.error))
    result.searches.append(("seed:search_knowledge", query[:200]))
    doc_q = (found_.by_source or {}).get("documents")
    if doc_q is not None and doc_q.rescue_called:
        result.calls.append(CallStat("rescue", None, None, int((clock() - t0) * 1000),
                                     "rescue-judge", None, ""))
    seed = [_present(found_, reg)]
    point_seed: dict[int, dict] = {}
    if asked_points:
        t0 = clock()
        point_seed = {p.n: _present(r, reg) for p, r in zip(
            asked_points, _search_points(ctx, asked_points), strict=True)}
        result.stages_ms["points_search"] = int((clock() - t0) * 1000)
    if lean:
        # no decision step will call `search_attachment`, so material past the inline
        # cap is searched here, with the message, one attachment at a time
        for att in tools.run(ctx, "list_attachments", {}).attachments:
            if att.get("status") == "READY":
                seed.append(_present(tools.run(ctx, "search_attachment", {
                    "attachment_id": att["attachment_id"], "query": query}), reg))
    # P2b: the kinds of agreement this conversation is about, from its own words only.
    instruments = agent_verify.instruments_in(
        message, *(c for r, c in thread.window if r.upper() == "USER"),
        *(e.text for e in reg.evidence().values() if e.source == "attachments"))
    # the figures the reader stated this turn: one an answer DENIES is not its own claim
    reader_figures = frozenset(agent_verify.reader_figures(message))
    document, executed = _selected_document(ctx)
    # Built ONCE per turn; every later call appends to it. The provider caches the
    # stable prefix itself — measured 2026-10-05: 32.7k–34.9k of ~35k input tokens
    # cached on the decision calls and the repair; the one miss is the first
    # schema-mode call (no tools, so a different request prefix). A local cache would
    # save nothing: the cost is in sending, not in formatting.
    # lean: each page carries only its own points' evidence (below) — all 17 at once was
    # ~50k tokens, past what Bonsai reads before its 50 s stream wait (2026-10-07)
    reviewing = bool(_REVIEW.search(message)) and (ctx.contract_id is not None
                                                   or has_material)
    # `AM-142`: the shared reader's "weighs our position" is the comparison too, so the
    # file's clauses are set beside our positions in code, never judged in prose
    comparing = reviewing or ((bool(_COMPARE.search(message))
                               or intent.weighs_our_position(message))
                              and (ctx.contract_id is not None or has_material))
    contents = _context(ctx, thread, pinned, material, message, document=document,
                        seed=seed, asked_points=asked_points,
                        point_seed=None if lean else point_seed, review=reviewing)
    result.stages_ms["context"] = int((clock() - t) * 1000)

    provider_down, last, repeat, asked = False, None, False, False
    brief: str | None = None
    # the per-point searches are the plan when points were asked; lean has no loop
    for step in range(0 if lean or asked_points else MAX_DECISIONS):
        stop = _should_stop(result, clock() - started, last=last, repeat=repeat,
                            asked=asked)
        if stop:
            result.flags.append(stop)
            break
        t = clock()
        try:
            # The first step always searches (2026-10-06): the model writes the turn's
            # queries from the whole conversation — "does that change the legal
            # situation?" carries no topic of its own, and with the step optional the
            # law was never searched in a 19-turn data-protection conversation.
            turn = provider.turn(SYSTEM_CONTRACT, contents, tools=TOOL_DECLARATIONS,
                                 schema=None,
                                 timeout_s=max(1.0, left() - FINAL_RESERVE_S),
                                 request_id=request_id, force_tool=step == 0)
        except (generation.GenerationRefused, generation.GenerationUnavailable) as exc:
            result.flags.append(f"decision_failed:{type(exc).__name__}: {exc}"[:120])
            provider_down = True
            break
        result.calls.append(_stat("decision", turn))
        result.results.append(turn)
        result.stages_ms[f"decision_{step + 1}"] = int((clock() - t) * 1000)
        last = turn
        if not turn.function_calls:
            continue                           # the model has what it needs
        contents.append({"role": "model", "parts": list(turn.parts)})
        responses, before, returned = [], set(reg.shown), 0
        t = clock()
        calls = [(fc.get("name", ""), fc.get("args") or {}) for fc in turn.function_calls]
        room = max(0, MAX_TOOL_EXECS - len(result.tool_execs))
        ran = _run_tools(ctx, calls[:room], clock)
        for i, (name, args) in enumerate(calls):
            if i >= room:
                result.flags.append("tool_cap")
                payload: dict = {"error": "TOOL_BUDGET_EXHAUSTED"}
            else:
                r, ms = ran[i]
                result.tool_execs.append((name, ms, r.error))
                result.searches.append((name, str(args.get("query")
                                                  or args.get("topic") or "")[:200]))
                payload = _present(r, reg)
                returned += len(r.records)
                asked = asked or (name == "ask_user" and not r.error)
                # the step's only call (`AM-200` r3): beside a search, the model is still
                # answering the question, and its results are not thrown away
                if name == "show_capabilities" and not r.error and len(calls) == 1:
                    brief = _capability_text(message)
            responses.append({"functionResponse": {"name": name, "response": payload}})
        contents.append({"role": "user", "parts": responses})
        if brief is not None:
            # the manifest as the fixed route renders it: the model chose the route,
            # code wrote the words (`AM-68` r3, `AM-200` r3)
            result.blocks, result.outcome, result.rung = (
                [{"kind": "prerouted", "text": brief, "cites": []}], "prerouted",
                "capability_tool")
            result.stages_ms["total"] = int((clock() - started) * 1000)
            return result
        result.stages_ms[f"tools_{step + 1}"] = int((clock() - t) * 1000)
        repeat = returned > 0 and set(reg.shown) <= before
        if returned and not getattr(provider, "done_check", True):
            result.flags.append("searched")     # no second look (`Model.done_check`)
            break

    final_text = None
    t = clock()
    if provider_down:
        result.flags.append("floor:provider")
    elif asked_points and left() > 1.0:
        final_text = _answer_points(provider, contents, result, request_id, left,
                                    asked_points, lean, language, message,
                                    point_seed if lean else None)
    elif len(result.calls) < MAX_CALLS and left() > 1.0:
        contents.append({"role": "user", "parts": [{"text": _final_instruction(
            language, message, review=reviewing, compare=comparing)}]})
        final_text = _final(provider, contents, result, request_id, left,
                            schema=answer_schema(reg.shown))
    else:
        result.flags.append("hard_deadline")
    result.stages_ms["final"] = int((clock() - t) * 1000)

    document_selected = ctx.contract_id is not None
    # the selected document's text missing or incomplete (R2, below), and whether it was
    # read whole — only then may a claim say what it does not state (`_checked_part`)
    selected = tools.selected_version(ctx)
    gap = tools.document_gap(ctx.db, selected) if selected is not None else None
    parsed = _parse(final_text)
    if parsed is None and final_text and (kept := _finished_blocks(final_text)):
        # the model's output limit cut the JSON off (DeepSeek wrote 28–40 blocks for a
        # review and hit 4,096 tokens): the blocks it FINISHED go through every check
        # below like any others, and the reader is told it stops short — a floor that
        # quotes one clause was the alternative (2026-10-08)
        parsed = _parse(kept)
        result.flags.append("cut")
    shown = reg.evidence()
    # the checks' own time, logged: a 3,375-token DeepSeek review spent ~49 s after its
    # answer call that no stage named (2026-10-08)
    post_started: float | None = None
    label = getattr(provider, "label", "") or None
    if parsed is None:
        # D2: the floor says why — the model did not finish, or its answer was unreadable
        reason = agent_verify.floor_reason(result.flags, [], [], shown, model=label,
                                           unreadable=bool(final_text))
        result.blocks = agent_verify.floor(shown, document_selected=document_selected,
                                           message=message, language=language,
                                           instruments=instruments, reason=reason)
        result.outcome, result.rung = "floor", "floor"
        _log_floor(request_id, reason, result.flags, [])
    else:
        verify_started = clock()
        claim = _claim_made(message)
        blocks = uncited_gaps_as_reasoning(agent_verify.normalise(parsed[0]))
        if asked_points:              # a model that numbers no block (DeepSeek, AM-202)
            blocks = points.assign_points(blocks, asked_points)
        assess = agent_verify.assessment(blocks, shown, claim_made=claim,
                                         proposed=parsed[1])
        # what every check of this turn is told, in one place: a context added to one
        # call and missed in another is a check that passes where it should not (P2b in
        # `settle`)
        context: dict[str, Any] = {
            "document_selected": document_selected, "document_executed": executed,
            "reply_language": language, "instruments": instruments,
            "reader_figures": reader_figures, "brand": ctx.brand,
            # the whole selected text, read without a gap, for a claim of what it lacks
            "document_passages": (tools.document_passages(ctx.db, selected)
                                  if selected is not None and gap is None else ()),
            # the reader's figures from earlier turns, for a draft only (V19)
            "conversation_figures": frozenset().union(*(
                agent_verify.reader_figures(c) for r, c in thread.window
                if r.upper() == "USER"))}
        found = agent_verify.verify(blocks, shown, assessment=assess, **context)
        found += agent_verify.unwritten(_analysis(final_text), blocks, shown)
        if writing and not any(b["kind"] == "draft" for b in blocks):
            # W1 (`AM-235`): asked for an email, wrote none — the one repair writes it
            found.append(agent_verify.Violation(
                len(blocks), "W1", "the user asked you to write something to send and "
                "no block is a draft — write it in full as a draft block"))
        result.violations_first = [x.line() for x in found]
        result.stages_ms["verify"] = int((clock() - verify_started) * 1000)
        t = clock()
        # the repair runs only with half as long again as the answer call just took: a
        # repair cut off by the budget ships exactly what skipping it ships — measured
        # on Bonsai, the same answer 40 s later; a 51 s answer whose repair was still
        # unfinished at 56 s; DeepSeek's repair started with ~5 s left and timed out
        # twice (D5, 2026-10-07)
        spent = (REPAIR_FACTOR * (result.calls[-1].latency_ms or 0) / 1000
                 if result.calls else 0.0)
        # points: no whole-answer repair — `settle` drops a failing sentence, and a point
        # left with none is asked again on its own below
        if (found and not asked_points and len(result.calls) < MAX_CALLS
                and left() > max(2.0, spent)):
            # Ask plan 4.2: ONE combined repair call — every violation, listed.
            contents.append({"role": "model", "parts": [{"text": final_text or ""}]})
            contents.append({"role": "user", "parts": [{"text": REPAIR_INSTRUCTION + "\n"
                             + "\n".join(f"- {x.line()}" for x in found) + "\n\n"
                             + _final_instruction(language, message,
                                                  review=reviewing, compare=comparing)}]})
            repaired = _parse(_final(provider, contents, result, request_id, left,
                                     role="repair", schema=answer_schema(reg.shown)))
            if repaired is not None:
                blocks = agent_verify.normalise(repaired[0])
                assess = agent_verify.assessment(blocks, shown, claim_made=claim,
                                                 proposed=repaired[1])
                found = agent_verify.verify(blocks, shown, assessment=assess, **context)
        result.stages_ms["repair"] = int((clock() - t) * 1000)
        post_started = clock()
        result.violations_final = [x.line() for x in found]
        checked = blocks                   # what `found` refers to, for D2's floor line
        blocks, result.dropped = agent_verify.settle(
            blocks, shown, found, reasons=result.drop_reasons,
            document_selected=document_selected,
            document_executed=executed, instruments=instruments,
            reader_figures=reader_figures, brand=ctx.brand,
            conversation_figures=context["conversation_figures"],
            document_passages=context["document_passages"])
        blocks = agent_verify.attribute_readings(blocks, shown)
        blocks = agent_verify.defer_interactions(blocks, shown)
        if not _WHOLE.search(message):
            # the four headings only where the reader asked about the whole situation —
            # the model filed parts on nearly every turn (final validation, 2026-10-06)
            blocks = [{k: v for k, v in b.items() if k != "part"} for b in blocks]
        # the same offer, "counsel must review" line or point, said again, is
        # boilerplate — kept only when the reader asks for the whole situation or to
        # hear it again (`AM-235`)
        blocks = agent_verify.fresh(blocks, replies,
                                    keep_review=bool(_WHOLE.search(message)),
                                    again=asks_again(message, thread.window))
        # the count stays in the turn's record and logs; the reader is not told about
        # the verifier's work (owner, 2026-10-05: no internal language in an answer)
        if limited(message, review=reviewing, points=bool(asked_points)):
            blocks = kept_to(blocks)
        if document_selected:
            blocks = agent_verify.document_first(blocks, shown)
            if agent_verify.asks_exit(message):
                shown = _exit_recall(ctx, reg, blocks, shown)
                blocks = agent_verify.exit_costs(blocks, shown, message)
        blocks = agent_verify.without_offers(blocks)
        reason = agent_verify.floor_reason(result.flags, found, checked, shown,
                                           model=label)
        blocks, result.rung = agent_verify.ladder(blocks, shown,
                                                  document_selected=document_selected,
                                                  message=message, language=language,
                                                  instruments=instruments,
                                                  reason=reason)
        if result.rung == "floor":
            _log_floor(request_id, reason, result.flags, found)
        if asked_points and result.rung != "floor":
            blocks = _cover_points(provider, contents, result, request_id, left,
                                   asked_points, blocks, shown, lean, language, message,
                                   {**context, "assessment": assess},
                                   point_seed if lean else None)
        if result.rung != "floor" and agent_verify.asks_remedy(message):
            # the brand the reader names, else the selected document's own (C-19): a
            # CloudPe SLA's credit question is answered with CloudPe's table alone
            from legalmind.assist.knowledge import published
            doc_brand = ctx.brand or published.document_brand(ctx.db,
                                                               tools.selected_version(ctx))
            if not agent_verify.schedules(shown):
                # the schedule an SLA remedy question needs, when the turn's searches
                # ranked only §11's prose: bulleted asks found the live SLA's credit
                # table 0 times in 3 (2026-10-15). Local retrieval, no model call.
                brand = " ".join(b for b in agent_verify.BRANDS if b in message.lower()
                                 ) or (doc_brand or "").lower()
                _present(tools.run(ctx, "search_knowledge", {
                    "query": f"{brand} {SCHEDULE_QUERY}".strip(), "k": 3,
                    "sources": ["constitution"]}), reg)
                shown = reg.evidence()
            blocks = agent_verify.with_schedule(blocks, shown, message, point=next(
                (p.n for p in asked_points if agent_verify.asks_remedy(p.text)), None),
                brand=doc_brand)
        blocks = with_owners(blocks, points_asked=bool(asked_points),       # D4
                             point_texts={p.n: p.text for p in asked_points})
        caveat = agent_verify.enforceability_caveat(blocks, replies, language)
        if caveat:
            blocks.append({"kind": "next_step", "cites": [], "text": caveat})
        if "cut" in result.flags:
            blocks.append({"kind": "next_step", "cites": [],
                           "text": agent_verify.note("cut", language)})
        searched = agent_verify.searched_line(blocks, result.searches, language)
        if searched:
            blocks.append({"kind": "next_step", "cites": [], "text": searched})
        result.blocks = blocks
        result.violations_shipped = [
            x.line() for x in agent_verify.verify(blocks, shown, assessment=assess,
                                                  **context)]
        result.assessment = agent_verify.assessment(blocks, shown, claim_made=claim,
                                                    proposed=assess)
        if result.rung == "floor":
            result.outcome = "floor"
    if asked_points and result.outcome == "floor":
        # D1: a floor never drops the asked points silently — every one is named
        result.blocks.append({"kind": "next_step", "cites": [],
                              "text": points.missing_line(asked_points)})
        if lean:
            # measured twice (2026-10-07): Bonsai (~20 tokens/s) does not finish even a
            # two-point page of a long list inside the turn — say what helps
            result.blocks.append({"kind": "next_step", "cites": [], "text": (
                f"{label or 'This model'} is slow on a list this long. Choose Gemini or "
                "DeepSeek in the model menu, or ask about two points at a time.")})
        result.flags.append(f"points:0/{len(asked_points)}")
    # R2: the selected document's text missing or incomplete, said in code whatever the
    # model wrote — nothing to read leads the reply, unread pages close it
    if gap is not None:
        if gap.state in tools.NO_TEXT:
            # Nothing was read, so "the document does not state X" is unfounded — the
            # very claim an unread document invites (review, 2026-10-16). Dropped;
            # what other sources say stands, and the note below says why.
            result.blocks = [b for b in result.blocks
                             if not agent_verify.states_an_absence(b)]
        result.blocks.insert(0 if gap.state in tools.NO_TEXT else len(result.blocks), {
            "kind": "next_step", "cites": [], "text": agent_verify.note(
                "document_unread", language).format(tools.gap_reason(gap))})
        result.flags.append(f"doc:{gap.state}")
    if post_started is not None:
        result.stages_ms["post"] = int((clock() - post_started) * 1000)
    # Said once — when the material carrying the instruction is first shown — and not
    # on every later turn that re-reads the same material, where it was appended to
    # answers about something else entirely (2026-10-08). A key the ledger already
    # holds is material an earlier reply has already reported.
    injected = agent_verify.instructions_in(
        {k: e for k, e in reg.evidence().items() if k in reg.new})
    if injected:
        result.blocks.append({"kind": "next_step", "cites": [],
                              "text": agent_verify.INJECTION_NOTE.format(injected[0])})
    known = set(reg.shown)
    for b in result.blocks:
        for c in b.get("cites") or []:
            (result.cited if c in known else result.invalid_cites).append(c)
    result.shown = list(reg.shown)
    result.weak = [k for k, sh in reg.shown.items() if sh.weak]
    result.stages_ms["total"] = int((clock() - started) * 1000)
    return result


def _log_floor(request_id: str | None, reason: str | None, flags: list[str],
               found: list) -> None:
    """Every floor logged with its reason (D2): the kind, the provider flags and the
    verifier's check codes and block numbers — never a sentence of text (the log
    policy: identifiers, codes and counts only)."""
    from legalmind.observability.logs import log_event
    provider = [f for f in flags if f.startswith(agent_verify._PROVIDER_FAILED)
                or f in {"floor:provider", "hard_deadline"}]
    kind = ("provider" if provider
            else "unreadable" if reason and "could not read" in reason
            else "checks" if found else "unknown")
    log_event("assist.agent.floor", request_id=request_id, reason=kind,
              flags=",".join(provider),
              checks=",".join(f"{x.block}:{x.check}" for x in found))


#: Tools that read only committed corpora, so another session sees what this one does.
#: The attachment tools stay on the request's session: a paste saved by this request
#: is not committed yet.
PARALLEL_TOOLS = frozenset({"search_knowledge", "search_statutes",
                            "get_company_position", "find_documents"})


def _run_tools(ctx: tools.ToolContext, calls: list[tuple[str, dict]],
               clock: Callable[[], float] = time.monotonic,
               ) -> list[tuple[tools.ToolResult, float]]:
    """The calls of one step, each with its time in ms: in parallel, each on its own
    read-only session, when the session is bound to an engine (the API's) and the tool
    is in PARALLEL_TOOLS; one after another otherwise (a test's single connection).
    D5: DeepSeek's three searches of one step took 2.9 s in a row (2026-10-07)."""
    def one(c: tools.ToolContext, name: str, args: dict):
        t0 = clock()
        r = tools.run(c, name, args)
        return r, (clock() - t0) * 1000
    bind = ctx.db.get_bind()
    if not isinstance(bind, Engine) or len(calls) < 2:
        return [one(ctx, n, a) for n, a in calls]

    def worker(call: tuple[str, dict]):
        if call[0] not in PARALLEL_TOOLS:
            return None
        with Session(bind) as own:
            return one(dataclasses.replace(ctx, db=own), *call)
    with ThreadPoolExecutor(max_workers=POINT_SEARCH_WORKERS) as pool:
        done = list(pool.map(worker, calls))
    return [d or one(ctx, n, a) for d, (n, a) in zip(done, calls, strict=True)]


def _search_points(ctx: tools.ToolContext,
                   asked: list[points.Point]) -> list[tools.ToolResult]:
    """Each asked point searched on its own over the company sources and the law (D1),
    in parallel (`_run_tools`)."""
    return [r for r, _ in _run_tools(ctx, [("search_knowledge", {
        "query": p.text[:tools.MAX_QUERY_CHARS], "k": 3, "sources": POINT_SOURCES})
        for p in asked])]


def _which(page: list[points.Point]) -> str:
    return ", ".join(str(p.n) for p in page)


def _answer_points(provider: Provider, contents: list[dict], result: TurnResult,
                   request_id: str | None, left: Callable[[], float],
                   asked: list[points.Point], lean: bool, language: str,
                   message: str, page_seed: dict | None = None) -> str | None:
    """The answer to an asked list, page by page (D1): every point at once, or — lean —
    a few per call, while the budget leaves time for a page; the pages' blocks merged
    into one answer. A page never started is a point named as unanswered, later."""
    size = POINTS_PER_CALL_LEAN if lean else len(asked)
    merged: list[dict] = []
    notes: list[str] = []
    verdict = None
    for i in range(0, len(asked), size):
        page = asked[i:i + size]
        spent = (result.calls[-1].latency_ms or 0) / 1000 if result.calls and lean else 0
        if left() < max(2.0, spent):
            result.flags.append("points:budget")
            break
        evidence = ("EVIDENCE FOR THESE POINTS (search_knowledge, keyed by point):\n"
                    + json.dumps({str(p.n): page_seed.get(p.n) for p in page}) + "\n\n"
                    if page_seed else "")
        contents.append({"role": "user", "parts": [{"text": evidence + _final_instruction(
            language, message, points=True) + "\n" + POINTS_INSTRUCTION.format(
                which=_which(page), asks=POINTS_ASK_MESSAGE if result.points_in_message
                else POINTS_ASK_MATERIAL)}]})
        raw = _final(provider, contents, result, request_id, left, answer_tokens=(
            POINTS_PAGE_TOKENS_LEAN if lean else POINTS_ANSWER_TOKENS))
        got = _parse(raw)
        if got is None:
            continue
        contents.append({"role": "model", "parts": [{"text": raw or ""}]})
        merged += got[0]
        notes.append(_analysis(raw))
        verdict = verdict or got[1]
    if not merged:
        return None
    return json.dumps({"analysis": " ".join(notes), "blocks": merged,
                       "assessment": verdict or "n/a"})


def _cover_points(provider: Provider, contents: list[dict], result: TurnResult,
                  request_id: str | None, left: Callable[[], float],
                  asked: list[points.Point], blocks: list[dict], shown: dict,
                  lean: bool, language: str, message: str, checks: dict,
                  page_seed: dict | None = None) -> list[dict]:
    """D1's count, after every check: requested against answered. A point no verified
    block answers is asked again on its own while the budget allows; one still
    unanswered is NAMED at the end, never dropped. The reply opens with the count, and
    the points stand in the reader's order."""
    # Points read from the message are the reader's own question: a block restating one
    # repeats the e-mail back and, cited, names a file for words that are not in it —
    # the model did so despite the instruction (2026-10-14, 1 run in 2). Removed in code.
    def restated(bs: list[dict]) -> list[dict]:
        return [b for b in bs if not (result.points_in_message
                                      and b.get("kind") == "user_stated")]
    blocks = restated(blocks)
    done = points.answered(blocks, agent_verify.ANSWERING)
    missing = [p for p in asked if p.n not in done]
    # D7 (`AM-204`): a re-ask starts only with as much time left as the last call took —
    # the lean pages' rule; one started on 2 s gets FINAL_MIN_S and overruns the client
    last = (result.calls[-1].latency_ms or 0) / 1000 if result.calls else 0.0
    if missing and left() <= max(2.0, last):
        result.flags.append("points:no_time")
    if missing and left() > max(2.0, last):
        raw = _answer_points(provider, contents, result, request_id, left, missing,
                             lean, language, message, page_seed)
        again = _parse(raw)
        if again is not None:
            extra = points.assign_points(uncited_gaps_as_reasoning(
                agent_verify.normalise(again[0])), missing)
            # judged with the answer it joins: an uncited block beside its cited
            # blocks is the allowed lead, not an answer that cites nothing (V5)
            found = agent_verify.verify(extra, shown, **checks, answer=blocks + extra)
            extra, dropped = agent_verify.settle(
                extra, shown, found, reasons=result.drop_reasons, context=blocks,
                document_selected=checks["document_selected"],
                document_executed=checks["document_executed"],
                instruments=checks["instruments"],
                reader_figures=checks["reader_figures"], brand=checks.get("brand"),
                conversation_figures=checks.get("conversation_figures", frozenset()),
                document_passages=checks.get("document_passages", ()))
            result.dropped += dropped
            wanted = {p.n for p in missing}
            # a re-ask that only restates the point again adds nothing (2026-10-14: the
            # same "your material states" bullet was shown twice)
            seen = {(b.get("point"), b.get("text")) for b in blocks}
            blocks = blocks + [b for b in restated(extra) if b.get("point") in wanted
                               and (b.get("point"), b.get("text")) not in seen]
            done = points.answered(blocks, agent_verify.ANSWERING)
            missing = [p for p in asked if p.n not in done]
    order = {p.n: i for i, p in enumerate(asked)}
    pointed = sorted((b for b in blocks if b.get("point") in order),
                     key=lambda b: order[b["point"]])
    rest = [b for b in blocks if b.get("point") not in order]
    result.flags.append(f"points:{len(done & set(order))}/{len(asked)}")
    subs = points.uncovered_subs(asked, blocks)
    if subs:                                     # D3 (`AM-202`): named, never silent
        result.flags.append(f"subs_uncovered:{len(subs)}")
    count = points.coverage_line(asked, done)
    return ([{"kind": "next_step", "cites": [], "text": count}] + pointed + rest
            + ([{"kind": "next_step", "cites": [], "text": points.missing_line(missing)}]
               if missing else [])
            + ([{"kind": "next_step", "cites": [], "text": points.uncovered_line(subs)}]
               if subs else []))


def _final(provider: Provider, contents: list[dict], result: TurnResult,
           request_id: str | None, left: Callable[[], float], *,
           role: str = "final", answer_tokens: int | None = None,
           schema: dict = ANSWER_SCHEMA) -> str | None:
    """A tool-free call with the §5.6 schema — the final answer or its one repair."""
    # only when set: a provider (or a test double) without the argument still answers
    budget: dict[str, Any] = {"answer_tokens": answer_tokens} if answer_tokens else {}
    floor_s = FINAL_MIN_S if role == "final" else 1.0
    try:
        turn = provider.turn(SYSTEM_CONTRACT, contents, tools=None, schema=schema,
                             timeout_s=max(floor_s, left()), request_id=request_id,
                             **budget)
    except (generation.GenerationRefused, generation.GenerationUnavailable) as exc:
        # the cause too ("TimeoutError", "HTTP 520") — D2's floor line rests on it
        result.flags.append(f"{role}_failed:{type(exc).__name__}: {exc}"[:120])
        return None
    result.calls.append(_stat(role, turn))
    result.results.append(turn)
    return turn.text


def _stat(role: str, r: generation.TurnResult) -> CallStat:
    return CallStat(role, r.prompt_tokens, r.output_tokens, r.latency_ms, r.model,
                    r.model_version, r.payload_sha256, r.cached_tokens,
                    r.reasoning_tokens)


def turn_log(turn: TurnResult) -> dict[str, Any]:
    """A turn as log fields — ids, counts, tokens and milliseconds, never text (53.3):
    the stage timings and each call's latency and tokens (cached, reasoning) that the
    2026-10-07 latency diagnosis found production could not see."""
    calls = turn.calls
    return {"outcome": turn.outcome, "rung": turn.rung, "calls": str(len(calls)),
            "brand": turn.brand or "",
            "tool_execs": str(len(turn.tool_execs)), "cited": ",".join(turn.cited),
            "weak_cited": str(len(turn.weak_cited)),
            "invalid_cites": str(len(turn.invalid_cites)),
            "prompt_tokens": str(sum(c.prompt_tokens or 0 for c in calls)),
            "output_tokens": str(sum(c.output_tokens or 0 for c in calls)),
            "total_ms": str(turn.stages_ms.get("total", 0)), "stages_ms": turn.stages_ms,
            "call_stats": [[c.role, c.latency_ms, c.prompt_tokens, c.output_tokens,
                            c.cached_tokens, c.reasoning_tokens] for c in calls],
            "tool_ms": [[name, round(ms)] for name, ms, _ in turn.tool_execs],
            "kinds": ",".join(b["kind"] for b in turn.blocks),
            "flags": ",".join(turn.flags),
            # which check fired on which block, codes only: a dropped opening block
            # left "The other notice periods…" with no trace of why (2026-10-08)
            "checks_first": _codes(turn.violations_first),
            "checks_final": _codes(turn.violations_final), "dropped": str(turn.dropped),
            "checks_dropped": ",".join(turn.drop_reasons),
            "nli": turn.nli}


def _codes(lines: list[str]) -> str:
    """'block 2: V4 — …' lines as '2:V4', the detail (which may quote) left out."""
    return ",".join(":".join(m.groups()) for line in lines
                    if (m := re.match(r"block (\d+): (\S+)", line)))


def _analysis(raw: str | None) -> str:
    """The answer's internal `analysis` (never rendered), or ''."""
    try:
        return str(json.loads(raw or "").get("analysis") or "")
    except (ValueError, AttributeError):
        return ""


def _block(b: dict) -> dict:
    """One block of the model's answer. A `comparison` becomes a SOURCED block carrying
    a `compare` object — so ordering, the ledger, the Sources list and the ladder treat
    it as the grounded claim it is — cited to exactly its two records; one missing a
    field is dropped, not guessed (fail closed)."""
    block = {"kind": b.get("kind"), "text": str(b.get("text", "")).strip(),
             "cites": [str(c) for c in (b.get("cites") or [])],
             **({"part": b["part"]} if b.get("part") in agent_verify.PARTS else {}),
             **({"point": b["point"]} if isinstance(b.get("point"), int) else {})}
    if block["kind"] == "comparison":
        fields = {k: str(b.get(k) or "").strip()
                  for k in ("agreement", "agreement_cite", "standard", "standard_cite")}
        if not all(fields.values()):
            return {**block, "kind": None}
        block.update(kind="sourced",
                     cites=[fields["agreement_cite"], fields["standard_cite"]],
                     compare=fields)
    return block


def _finished_blocks(raw: str) -> str | None:
    """The `blocks` a cut-off answer finished, as the JSON the parser expects — None
    when it finished none. A model that reaches its output limit leaves the document
    open; each block before the cut is whole and is judged like any other."""
    at = raw.find('"blocks"')
    at = raw.find("[", at) if at >= 0 else -1
    if at < 0:
        return None
    decoder, i, found = json.JSONDecoder(), at + 1, []
    while True:
        while i < len(raw) and raw[i] in " \n\r\t,":
            i += 1
        if i >= len(raw) or raw[i] != "{":
            break
        try:
            block, i = decoder.raw_decode(raw, i)
        except ValueError:
            break
        found.append(block)
    return json.dumps({"blocks": found}) if found else None


def _parse(raw: str | None) -> tuple[list[dict], str] | None:
    """The final answer, or None when it is not the required structure."""
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    blocks = [_block(b) for b in data.get("blocks") or [] if isinstance(b, dict)]
    blocks = [b for b in blocks if b["kind"] in KINDS and (b["text"] or b.get("compare"))]
    if not blocks:
        return None
    assessment = data.get("assessment")
    return blocks, assessment if assessment in ASSESSMENTS else "n/a"


# ---------------------------------------------------------------------- shadow (service)
def shadow(db, *, conversation_id: UUID, user_id: UUID, permissions: frozenset[str],
           message: str, request_id: str | None,
           provider: Provider | None = None) -> TurnResult | None:
    """B6: run the agent BESIDE the shipped answer and log only ids, hashes, counts,
    tokens and latencies. Its output is returned to the caller for logging and NEVER
    reaches a reader. Writes nothing except the egress audit rows (AM-30 t5)."""
    from legalmind.observability.logs import log_event
    savepoint = db.begin_nested()
    try:
        ctx = tools.ToolContext.open(db, user_id=user_id, permissions=permissions,
                                     conversation_id=conversation_id)
        turn = run_turn(provider or GeminiProvider(), ctx, message,
                        request_id=request_id)
    except Exception as exc:                    # shadow must never break the answer
        savepoint.rollback()
        log_event("assist.agent.shadow_failed", request_id=request_id,
                  error=type(exc).__name__)
        return None
    savepoint.rollback()
    _audit(db, turn, conversation_id, request_id)
    log_event("assist.agent.shadow", request_id=request_id,
              conversation_id=str(conversation_id), **turn_log(turn))
    return turn


def _audit(db, turn: TurnResult, conversation_id: UUID, request_id: str | None) -> None:
    """Every agent call audited with provider, model and served version (B1, AM-30 t5)."""
    from legalmind.assist import service
    service._audit_calls(db, turn.results, conversation_id, request_id,
                         len(turn.shown))
