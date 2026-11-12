"""LA-4 (owner, 2026-11-09): a reader never sees the `[our wording sha256:…]` tag an
approval carries (`AM-284` r2) — plain words instead; the stored row keeps the hash."""
import uuid

from legalmind.api.serializers import serialize_decision
from legalmind.db import models as M
from legalmind.domain.enums import DecisionType
from legalmind.workflow.decisions import reader_justification, wording_tag

TAG = wording_tag("ab" * 32)


def test_the_tag_reads_as_plain_words_and_the_record_keeps_the_hash():
    stored = f"Keep the indemnity to third-party claims {TAG}"
    d = M.LegalDecision(id=uuid.uuid4(), evaluation_id=uuid.uuid4(), finding_id=uuid.uuid4(),
                        decision_type=DecisionType.APPROVE_CUSTOMIZATION,
                        justification=stored, decided_by=uuid.uuid4(), version_number=1)
    shown = serialize_decision(d)["justification"]
    assert shown == "Keep the indemnity to third-party claims (our approved wording)"
    assert "sha256" not in shown and d.justification == stored


def test_a_reason_without_a_tag_is_unchanged():
    assert reader_justification("small deal [see clause 9]") == "small deal [see clause 9]"
