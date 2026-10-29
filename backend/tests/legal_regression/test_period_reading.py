"""QA-018/019/020 (2026-10-29): a period clause is read as the term it states — never
"Missing" when it is there, never another period's figure. Synthetic clauses only
(54.6), read by the real ratified standards."""

from __future__ import annotations

from tests.legal_regression.test_evidence_gated import _read


def _read_as(code: str, *texts: str) -> list[tuple]:
    caps, _ = _read(code, *texts)
    return [(c.cap_status, c.cap_value, c.cap_unit, c.reason) for c in caps]


def test_survival_without_the_article_is_read():
    """QA-020: "survive termination of this Agreement" is "survive the termination …"
    (the equivalence table), so the standard's own phrase reads it."""
    text = ("3.1 The obligations of confidentiality shall survive termination of this "
            "Agreement for a period of {} .")
    assert _read_as("CONF-SURVIVAL-MSA-001", text.format("three (3) years")) == [
        ("FINITE", 3.0, "YEARS", None)]
    assert _read_as("CONF-SURVIVAL-MSA-001", text.format("thirty-six (36) months")) == [
        ("FINITE", 36.0, "MONTHS", None)]


def test_a_period_in_working_days_is_read_as_working_days_never_missing():
    """QA-018 / AM-154: business days are not calendar days, and are never "Missing"."""
    assert _read_as("DISPUTE-WINDOW-MSA-001",
                    "3.1 Billing disputes must be raised within fifteen (15) business "
                    "days of the invoice date.") == [
        ("WORKING_DAYS", 15.0, "WORKING_DAYS", None)]


def test_a_period_in_a_unit_the_standard_does_not_read_is_unread_never_missing():
    """QA-018: three weeks beside a DAYS standard is found and its figure left to a
    person — not converted (no declared WEEKS pair), not "not in the contract"."""
    [(status, _, _, reason)] = _read_as(
        "PAYMENT-PERIOD-MSA-001",
        "3.1 Invoices are payable within three (3) weeks of the invoice date.")
    assert (status, reason) == ("UNKNOWN", "FIGURE_NOT_READ")


def test_the_dispute_window_is_never_the_payment_period():
    """QA-019: the dispute sentence names the invoice date too; it states the dispute
    window (its own standard), so the payment period reads only the payment sentence."""
    assert _read_as("PAYMENT-PERIOD-MSA-001",
                    "3.1 Invoices are payable within twenty-one (21) days of the invoice "
                    "date. Billing disputes must be raised within fifteen (15) days of the "
                    "invoice date.") == [("FINITE", 21.0, "DAYS", None)]
    assert _read_as("PAYMENT-PERIOD-MSA-001",
                    "3.2 Billing disputes must be raised within fifteen (15) business days "
                    "of the invoice date.") == []


def test_a_payment_clause_in_weeks_is_not_the_dispute_window():
    """A topic word alone ("invoice") names the dispute window's neighbours too: a
    figure in another unit counts only beside the term's own basis words."""
    assert [s for s, *_ in _read_as(
        "DISPUTE-WINDOW-MSA-001",
        "3.1 Invoices are payable within three (3) weeks of the invoice date.")] == ["ABSENT"]
