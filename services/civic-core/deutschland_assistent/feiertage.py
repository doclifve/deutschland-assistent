"""Gesetzliche Feiertage in Deutschland für die Fristberechnung.

Fällt das Ende einer Frist auf einen Sonnabend, Sonntag oder gesetzlichen Feiertag, endet sie mit Ablauf des
nächsten Werktags (§ 193 BGB, § 31 Abs. 3 VwVfG, § 26 Abs. 3 SGB X, § 108 Abs. 3 AO, § 222 Abs. 2 ZPO).
Maßgeblich ist der Feiertag am Ort der Behörde bzw. des Gerichts.

Die Regeln folgen den Feiertagsgesetzen der Länder (Stand 2026) und werden offline berechnet, damit keine
Laufzeitabhängigkeit von externen Diensten entsteht. Feiertage, die nur in einzelnen Gemeinden gelten, stehen in
``regional_holidays``: Sie verlängern eine Frist nie automatisch, sondern führen nur zu einem Hinweis.
"""
from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache

STATES: dict[str, str] = {
    "BW": "Baden-Württemberg",
    "BY": "Bayern",
    "BE": "Berlin",
    "BB": "Brandenburg",
    "HB": "Bremen",
    "HH": "Hamburg",
    "HE": "Hessen",
    "MV": "Mecklenburg-Vorpommern",
    "NI": "Niedersachsen",
    "NW": "Nordrhein-Westfalen",
    "RP": "Rheinland-Pfalz",
    "SL": "Saarland",
    "SN": "Sachsen",
    "ST": "Sachsen-Anhalt",
    "SH": "Schleswig-Holstein",
    "TH": "Thüringen",
}


def easter_sunday(year: int) -> date:
    """Ostersonntag nach dem gregorianischen Kalender (anonymer gregorianischer Algorithmus)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7  # noqa: E741 - Bezeichnung aus dem Algorithmus
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def _buss_und_bettag(year: int) -> date:
    """Mittwoch vor dem 23. November."""
    nov22 = date(year, 11, 22)
    return nov22 - timedelta(days=(nov22.weekday() - 2) % 7)


@lru_cache(maxsize=64)
def nationwide_holidays(year: int) -> dict[date, str]:
    easter = easter_sunday(year)
    days = {
        date(year, 1, 1): "Neujahr",
        easter - timedelta(days=2): "Karfreitag",
        easter + timedelta(days=1): "Ostermontag",
        date(year, 5, 1): "Tag der Arbeit",
        easter + timedelta(days=39): "Christi Himmelfahrt",
        easter + timedelta(days=50): "Pfingstmontag",
        date(year, 12, 25): "1. Weihnachtstag",
        date(year, 12, 26): "2. Weihnachtstag",
    }
    if year >= 1990:
        days[date(year, 10, 3)] = "Tag der Deutschen Einheit"
    if year == 2017:
        days[date(2017, 10, 31)] = "Reformationstag (500. Jahrestag, bundesweit)"
    return days


@lru_cache(maxsize=512)
def state_holidays(year: int, state: str) -> dict[date, str]:
    """Alle landesweit geltenden Feiertage eines Bundeslands (inklusive der bundesweiten)."""
    state = state.upper()
    if state not in STATES:
        raise ValueError(f"Unbekanntes Bundesland: {state}")
    easter = easter_sunday(year)
    days = dict(nationwide_holidays(year))

    def add(states: set[str], day: date, name: str, since: int | None = None) -> None:
        if state in states and (since is None or year >= since):
            days[day] = name

    add({"BW", "BY", "ST"}, date(year, 1, 6), "Heilige Drei Könige")
    add({"BE"}, date(year, 3, 8), "Internationaler Frauentag", since=2019)
    add({"MV"}, date(year, 3, 8), "Internationaler Frauentag", since=2023)
    add({"BB"}, easter, "Ostersonntag")
    add({"BB"}, easter + timedelta(days=49), "Pfingstsonntag")
    add({"BW", "BY", "HE", "NW", "RP", "SL"}, easter + timedelta(days=60), "Fronleichnam")
    add({"SL"}, date(year, 8, 15), "Mariä Himmelfahrt")
    add({"TH"}, date(year, 9, 20), "Weltkindertag", since=2019)
    add({"BB", "MV", "SN", "ST", "TH"}, date(year, 10, 31), "Reformationstag")
    add({"HB", "HH", "NI", "SH"}, date(year, 10, 31), "Reformationstag", since=2018)
    add({"BW", "BY", "NW", "RP", "SL"}, date(year, 11, 1), "Allerheiligen")
    add({"SN"}, _buss_und_bettag(year), "Buß- und Bettag", since=1995)
    # Einmalige Feiertage in Berlin (Gesetz über die Sonn- und Feiertage)
    if state == "BE" and year in (2020, 2025):
        days[date(year, 5, 8)] = "Tag der Befreiung (einmalig)"
    if state == "BE" and year == 2028:
        days[date(2028, 6, 17)] = "75. Jahrestag des Volksaufstands vom 17. Juni 1953 (einmalig)"
    return days


@lru_cache(maxsize=512)
def regional_holidays(year: int, state: str) -> dict[date, str]:
    """Feiertage, die nur in Teilen eines Landes gelten. Verlängern Fristen nie automatisch."""
    state = state.upper()
    easter = easter_sunday(year)
    regional: dict[date, str] = {}
    if state == "BY":
        regional[date(year, 8, 15)] = "Mariä Himmelfahrt (in Gemeinden mit überwiegend katholischer Bevölkerung)"
        regional[date(year, 8, 8)] = "Augsburger Friedensfest (nur Stadt Augsburg)"
    if state in {"SN", "TH"}:
        regional[easter + timedelta(days=60)] = "Fronleichnam (nur in einzelnen Gemeinden)"
    return regional


def holiday_name(day: date, state: str | None) -> str | None:
    """Name des Feiertags an ``day`` – landesweit, oder bundesweit, wenn das Land unbekannt ist."""
    table = state_holidays(day.year, state) if state else nationwide_holidays(day.year)
    return table.get(day)


def states_with_holiday(day: date) -> list[str]:
    """Bundesländer, in denen ``day`` landesweit gesetzlicher Feiertag ist."""
    return [code for code in STATES if day in state_holidays(day.year, code)]


def next_working_day(day: date, state: str | None = None) -> tuple[date, list[str]]:
    """Verschiebt ``day`` über Wochenenden und gesetzliche Feiertage.

    Gibt das Fristende und die Namen der übersprungenen Feiertage zurück. Ohne Bundesland zählen nur die
    bundesweiten Feiertage; das Ergebnis ist dann das frühestmögliche (sichere) Fristende.
    """
    skipped: list[str] = []
    while True:
        name = holiday_name(day, state)
        if name:
            skipped.append(f"{name} ({day.strftime('%d.%m.%Y')})")
        elif day.weekday() < 5:
            return day, skipped
        day += timedelta(days=1)


def deadline_notes(end: date, state: str | None) -> list[str]:
    """Hinweise, wenn das Fristende anderswo bzw. regional ein Feiertag ist (konservativ nicht verschoben)."""
    notes: list[str] = []
    if state is None:
        others = states_with_holiday(end)
        if others:
            names = ", ".join(STATES[s] for s in others)
            notes.append(
                f"Der {end.strftime('%d.%m.%Y')} ist in {names} gesetzlicher Feiertag. Sitzt die Behörde dort, "
                "endet die Frist erst am nächsten Werktag. Ohne Angabe des Bundeslands gilt vorsichtshalber das frühere Datum."
            )
    else:
        regional = regional_holidays(end.year, state).get(end)
        if regional:
            notes.append(
                f"Der {end.strftime('%d.%m.%Y')} ist regional Feiertag: {regional}. Gilt er am Sitz der Behörde, "
                "endet die Frist erst am nächsten Werktag. Vorsichtshalber gilt das frühere Datum."
            )
    return notes
