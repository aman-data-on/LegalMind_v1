"""Review, Q-11: the incident-reporting cue reads hours only beside a breach, an
incident, CERT-In or a report — never an SLA response time, a payment window or an
outage credit."""
import pytest

from legalmind.assist.query import planner


@pytest.mark.parametrize("q", [
    "Does support respond within 4 hours under the SLA?",
    "Customer must pay within 48 hours",
    "server kitne ghante down raha toh credit milega?",
])
def test_hours_alone_are_not_incident_reporting(q):
    plan = planner.plan_lexical(q)
    assert plan is None or plan.subject != "cyber incident reporting"


def test_the_hours_to_report_a_breach_are_incident_reporting_in_either_order():
    for q in ("data breach hua toh CERT-In ko kitne ghante me batana hai, aur customer "
              "ko bhi batana padega kya?",
              "How many hours do we have to report a data breach to CERT-In?"):
        assert planner.plan_lexical(q).subject == "cyber incident reporting"
