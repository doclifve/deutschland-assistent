"""Feiertage je Bundesland und ihre Wirkung auf das Fristende (§ 193 BGB, § 31 Abs. 3 VwVfG, § 26 Abs. 3 SGB X)."""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from deutschland_assistent.extraction import extract_relative_deadlines, next_weekday
from deutschland_assistent.feiertage import (
    STATES,
    _buss_und_bettag,
    deadline_notes,
    easter_sunday,
    next_working_day,
    regional_holidays,
    state_holidays,
    states_with_holiday,
)
from deutschland_assistent.main import app


@pytest.mark.parametrize(
    "year,expected",
    [(2000, date(2000, 4, 23)), (2019, date(2019, 4, 21)), (2024, date(2024, 3, 31)),
     (2025, date(2025, 4, 20)), (2026, date(2026, 4, 5)), (2027, date(2027, 3, 28))],
)
def test_easter(year, expected):
    assert easter_sunday(year) == expected


@pytest.mark.parametrize("year,expected", [(2024, date(2024, 11, 20)), (2025, date(2025, 11, 19)), (2026, date(2026, 11, 18))])
def test_buss_und_bettag(year, expected):
    assert _buss_und_bettag(year) == expected


# Anzahl landesweiter Feiertage 2026 laut Feiertagsgesetzen der Länder (inkl. 9 bundesweiter).
EXPECTED_2026 = {
    "BW": 12, "BY": 12, "BE": 10, "BB": 12, "HB": 10, "HH": 10, "HE": 10, "MV": 11,
    "NI": 10, "NW": 11, "RP": 11, "SL": 12, "SN": 11, "ST": 11, "SH": 10, "TH": 11,
}


def test_holiday_counts_2026_cover_all_states():
    assert set(EXPECTED_2026) == set(STATES)
    assert {s: len(state_holidays(2026, s)) for s in STATES} == EXPECTED_2026


def test_specific_state_rules():
    assert date(2026, 3, 8) in state_holidays(2026, "BE")
    assert date(2022, 3, 8) not in state_holidays(2022, "MV")  # erst seit 2023
    assert date(2023, 3, 8) in state_holidays(2023, "MV")
    assert date(2017, 10, 31) in state_holidays(2017, "BY")  # einmalig bundesweit
    assert date(2016, 10, 31) not in state_holidays(2016, "NI")  # NI erst seit 2018
    assert date(2025, 5, 8) in state_holidays(2025, "BE")
    assert date(2026, 5, 8) not in state_holidays(2026, "BE")
    assert date(2028, 6, 17) in state_holidays(2028, "BE")
    assert date(2026, 8, 15) in state_holidays(2026, "SL")
    assert date(2026, 8, 15) not in state_holidays(2026, "BY")
    assert date(2026, 8, 15) in regional_holidays(2026, "BY")
    assert date(2026, 6, 4) in state_holidays(2026, "NW")  # Fronleichnam
    assert date(2026, 6, 4) in regional_holidays(2026, "SN")
    assert set(states_with_holiday(date(2025, 10, 31))) == {"BB", "MV", "SN", "ST", "TH", "HB", "HH", "NI", "SH"}


def test_unknown_state_rejected():
    with pytest.raises(ValueError):
        state_holidays(2026, "XX")


def test_next_working_day_skips_easter_weekend():
    end, skipped = next_working_day(date(2026, 4, 3))  # Karfreitag
    assert end == date(2026, 4, 7)
    assert len(skipped) == 2 and "Karfreitag" in skipped[0] and "Ostermontag" in skipped[1]
    assert next_weekday(date(2026, 12, 25)) == date(2026, 12, 28)


def _bekanntgabe_2wochen(doc_date, state=None):
    return extract_relative_deadlines("binnen 2 Wochen nach Zugang", doc_date, state)[0]


def test_reformationstag_moves_deadline_only_where_it_is_a_holiday():
    # Schreiben 13.10.2025 → Zugang 17.10. (4-Tage-Fiktion) → Fristende Fr 31.10.2025
    doc = date(2025, 10, 13)
    assert _bekanntgabe_2wochen(doc, "BY").estimated_end == date(2025, 10, 31)
    ni = _bekanntgabe_2wochen(doc, "NI")
    assert ni.estimated_end == date(2025, 11, 3)
    assert ni.bundesland == "NI"
    assert any("Reformationstag" in b for b in ni.basis)
    unknown = _bekanntgabe_2wochen(doc)
    assert unknown.estimated_end == date(2025, 10, 31)  # konservativ: früheres Datum
    assert any("Niedersachsen" in b and "gesetzlicher Feiertag" in b for b in unknown.basis)


def test_nationwide_holiday_applies_without_state():
    # Schreiben 16.03.2026 → Zugang 20.03. → Fristende Karfreitag 03.04.2026 → Di 07.04.2026
    assert _bekanntgabe_2wochen(date(2026, 3, 16)).estimated_end == date(2026, 4, 7)


def test_buss_und_bettag_in_sachsen():
    # Schreiben 31.10.2026 → Zugang 04.11. → Fristende Mi 18.11.2026 (Buß- und Bettag in SN)
    assert _bekanntgabe_2wochen(date(2026, 10, 31), "SN").estimated_end == date(2026, 11, 19)
    assert _bekanntgabe_2wochen(date(2026, 10, 31), "BE").estimated_end == date(2026, 11, 18)


def test_regional_holiday_only_noted():
    notes = deadline_notes(date(2026, 8, 15), "BY")
    assert notes and "Mariä Himmelfahrt" in notes[0]


def test_invalid_state_in_extraction_is_ignored():
    assert _bekanntgabe_2wochen(date(2025, 10, 13), "XX").bundesland is None


client = TestClient(app)
LETTER = b"Datum: 13.10.2025\nGegen diesen Bescheid kann binnen 2 Wochen nach Zugang Widerspruch erhoben werden."


def test_upload_with_bundesland():
    r = client.post("/v1/documents", files={"file": ("brief.txt", LETTER, "text/plain")}, data={"bundesland": "ni"})
    assert r.status_code == 200
    rel = r.json()["relative_deadlines"][0]
    assert rel["estimated_end"] == "2025-11-03"
    assert rel["bundesland"] == "NI"


def test_upload_rejects_unknown_bundesland():
    r = client.post("/v1/documents", files={"file": ("brief.txt", LETTER, "text/plain")}, data={"bundesland": "Bayern"})
    assert r.status_code == 422
