"""`AM-229` (2026-10-28): a clause forbidding suspension waives the §16 position; one
forbidding it "without notice" states it. Synthetic text (54.6); no database, no model."""
import json
from pathlib import Path
from uuid import uuid4

from legalmind.analysis.service import waiver_signals
from legalmind.mapping.engine import Clause

CFG = json.loads((Path(__file__).parents[1] / "config/company_standards"
                  / "SUSPENSION-NOTICE-CURE-MSA-001.json").read_text())["configuration"]


def _signals(text):
    return waiver_signals([Clause(evidence_id=uuid4(), content=text, section_number="15")],
                          CFG["waiver_patterns"], 5, conditions=CFG["waiver_conditions"])


def test_forbidding_suspension_waives_the_position():
    assert _signals("The Provider shall not suspend, interrupt or restrict the Services "
                    "except where expressly required under Applicable Laws.")
    assert _signals("The Provider will not suspend Services solely on account of delayed "
                    "payment without complying with the termination process.")


def test_forbidding_suspension_without_notice_states_the_position():
    assert not _signals("The Provider shall not suspend the Services for non-payment "
                        "without prior written notice and a cure period.")
    assert not _signals("The Provider may suspend the Services for non-payment after "
                        "written notice and a reasonable opportunity to cure.")
