from datetime import date

from deutschland_assistent.extraction import (
    add_months,
    extract_deadlines,
    extract_document_date,
    extract_legal_references,
    extract_relative_deadlines,
    law_url,
)

BESCHEID = """Jobcenter Hamburg
Hamburg, den 13.09.2026

Bescheid über Leistungen nach dem SGB II

Rechtsbehelfsbelehrung
Gegen diesen Bescheid kann innerhalb eines Monats nach seiner Bekanntgabe Widerspruch erhoben werden.
Bitte beachten Sie § 60 SGB I und § 60 SGB I.
"""


def test_document_date():
    assert extract_document_date(BESCHEID) == date(2026, 9, 13)


def test_document_date_requires_marker():
    assert extract_document_date("Termin 13.09.2026") is None


def test_relative_deadline_month_with_weekend_shift():
    rd = extract_relative_deadlines(BESCHEID, date(2026, 9, 13))
    assert len(rd) == 1
    r = rd[0]
    assert (r.period_value, r.period_unit, r.trigger) == (1, "months", "Bekanntgabe")
    assert r.assumed_trigger_date == date(2026, 9, 17)  # vierter Tag nach Aufgabe zur Post
    assert r.estimated_end == date(2026, 10, 19)  # 17.10.2026 ist Samstag -> Montag
    assert r.confidence == "low"


def test_relative_deadline_before_2025_uses_three_days():
    r = extract_relative_deadlines("innerhalb eines Monats nach Bekanntgabe", date(2024, 12, 2))[0]
    assert r.assumed_trigger_date == date(2024, 12, 5)


def test_relative_deadline_weeks_and_digits():
    r = extract_relative_deadlines("binnen 2 Wochen nach Zugang", date(2026, 9, 10))[0]
    assert (r.period_value, r.period_unit) == (2, "weeks")
    assert r.estimated_end == date(2026, 9, 28)


def test_relative_deadline_without_document_date():
    r = extract_relative_deadlines("innerhalb von zwei Wochen nach Erhalt")[0]
    assert r.estimated_end is None and r.basis


def test_zustellung_not_estimated():
    r = extract_relative_deadlines("innerhalb eines Monats nach Zustellung", date(2026, 9, 10))[0]
    assert r.estimated_end is None


def test_month_end_clamp():
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)


def test_refs_deduplicated():
    refs = extract_legal_references(BESCHEID)
    assert [(r.section, r.law) for r in refs] == [("§ 60", "SGB I")]


def test_new_law_slugs():
    assert law_url("VwVfG", "§ 41") == "https://www.gesetze-im-internet.de/vwvfg/__41.html"
    assert law_url("SGG", "§ 84") == "https://www.gesetze-im-internet.de/sgg/__84.html"
    assert law_url("EStG", "§ 32a") == "https://www.gesetze-im-internet.de/estg/__32a.html"


def test_explicit_deadline():
    d = extract_deadlines("Bitte bis zum 21.10.2026 antworten.")
    assert d[0].date == date(2026, 10, 21) and d[0].confidence == "high"


def test_document_date_is_not_a_deadline():
    assert extract_deadlines(BESCHEID, date(2026, 9, 13)) == []
