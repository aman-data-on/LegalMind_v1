"""Phase 1 exit G1/G4 with the real model — spends Gemini calls (at most 3 per case).

    LEGALMIND_GATE_DBNAME=<scratch gate db> python3 -m tools.live_attachment_cases

A tool, not a test: tests never carry the production credential (`conftest` refuses
it). Runs against the Tier-2 gate's SCRATCH database (already migrated by
`verify_assist_quality`), through the API layer's own extraction and paste split and
`service.ask`, then ROLLS BACK — nothing persists. Synthetic text only (rule 21).
Prints states, call counts, tokens and the answer — the cases are synthetic text,
never client material.
"""
from __future__ import annotations

import uuid

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from legalmind import config
from legalmind.api.routers.assist import extract_material
from legalmind.assist import service
from legalmind.assist.agent import attachments
from legalmind.assist.llm import generation
from tools.verify_assist_quality import _gate_url

EMAIL = ("Subject: March outage and the service credit\n\n"
         "From the customer: the outage on 14 March lasted nine hours on the primary "
         "database cluster and breached the monthly availability commitment.\n\n"
         "We ask that a service credit of fifteen percent of the monthly fee be "
         "applied to the April invoice, before the renewal date.\n\n")
NOTE = (b"Renewal note. The agreement renews automatically for twelve months unless "
        b"either party gives sixty days written notice before the renewal date.")
ASK = frozenset({"assist.ask"})


def _add(db, conv, data: bytes, kind: str, filename=None, mime="text/plain"):
    mime, extracted = extract_material(data, kind, filename, mime)
    return attachments.add(db, conversation_id=conv, data=data, kind=kind, mime=mime,
                           extracted=extracted, filename=filename)


def main() -> int:
    import os
    os.environ["LEGALMIND_ASK_ATTACHMENTS"] = "on"
    calls: list[tuple[int, int]] = []
    real = generation.generate_raw

    def counted(*a, **k):
        if len(calls) >= 6:
            raise SystemExit("call cap (6) reached")      # refuse BEFORE spending
        result = real(*a, **k)
        calls.append((result.prompt_tokens or 0, result.output_tokens or 0))
        return result
    generation.generate_raw = counted

    engine = create_engine(_gate_url(), future=True)
    db = sessionmaker(bind=engine, future=True)()
    ok = True
    try:
        user = uuid.uuid4()
        db.execute(text("INSERT INTO users (id, email, name, status, created_at, "
                        "updated_at) VALUES (:i, :e, 'live cases', 'ACTIVE', now(), "
                        "now())"), {"i": user, "e": f"live-{user.hex[:12]}@leapswitch.com"})
        cases = []
        # G1 — a long paste, saved as material, the question split off and answered.
        conv = service.create_conversation(db, user_id=user, contract_id=None)
        question, material = attachments.split_paste(
            EMAIL * 6 + "How many hours did the outage last, and what credit is asked for?")
        saved = _add(db, conv, material.encode(), attachments.PASTE)
        cases.append(("G1", saved, conv, question, (("nine", "9"), ("fifteen", "15"))))
        # G4 — a .txt file, its status, then a question about it.
        conv = service.create_conversation(db, user_id=user, contract_id=None)
        saved = _add(db, conv, NOTE, attachments.FILE, "renewal.txt")
        cases.append(("G4", saved, conv,
                      "How many days of notice does the renewal note require?", (("sixty", "60"),)))
        only = set(filter(None, os.environ.get("LIVE_CASES", "").split(",")))
        for name, saved, conv, question, words in cases:
            if only and name not in only:
                continue
            before = len(calls)
            out = service.ask(db, conversation_id=conv, document_version_id=None,
                              question=question, permissions=ASK)
            low = out.text.lower()
            checks = {"status_ready": saved.status == "READY",
                      "answered": out.answer_state.value == "ANSWERED",
                      "from_material": all(any(w in low for w in alts) for alts in words),
                      "named_as_users": "user-provided" in out.text,
                      "not_the_contract": "the contract" not in low,
                      "calls<=3": len(calls) - before <= 3}
            ok &= all(checks.values())
            spent = calls[before:]
            print(f"{name} calls={len(spent)} prompt_tokens={sum(p for p, _ in spent)} "
                  f"output_tokens={sum(o for _, o in spent)} "
                  + " ".join(f"{k}={'PASS' if v else 'FAIL'}" for k, v in checks.items()))
            print(f"  answer: {out.text!r}")      # synthetic case text only (rule 21)
    finally:
        db.rollback()
        db.close()
        engine.dispose()
        generation.generate_raw = real
    print(f"total calls={len(calls)} schema={config.assist_schema()} rolled back")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
