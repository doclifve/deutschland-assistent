"""Prepare (never book) an appointment with a German authority.

The assistant finds the official service page, a Bundesportal search for the
person's postal code and a checklist of documents. The person books the
appointment themselves on the authority's own page. An automated booking
connector does not exist yet; a confirmed action only releases the official
booking link.
"""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from .schemas import AppointmentPlan, Link

DATA = Path(__file__).resolve().parent / "data" / "appointments.de.json"
BUNDESPORTAL_SEARCH = "https://verwaltung.bund.de/leistungsverzeichnis/de/suche"
POSTAL_CODE = re.compile(r"^\d{5}$")


@lru_cache(maxsize=1)
def concerns() -> list[dict]:
    return json.loads(DATA.read_text(encoding="utf-8"))


def _normalize(text: str) -> str:
    return " ".join(re.sub(r"[^\wäöüß-]+", " ", text.lower()).split())


def match_concern(text: str) -> dict | None:
    """Pick the concern whose keywords match best (whole words, longer phrases weigh more)."""
    normalized = f" {_normalize(text)} "
    best, best_score = None, 0
    for concern in concerns():
        if concern["id"] == _normalize(text):
            return concern
        score = sum(len(k) for k in concern["keywords"] if f" {_normalize(k)} " in normalized)
        if score > best_score:
            best, best_score = concern, score
    return best


def bundesportal_search_url(query: str, postal_code: str | None) -> str:
    params = {"query": query}
    if postal_code:
        params["postleitzahlOrt"] = postal_code
    return f"{BUNDESPORTAL_SEARCH}?{urlencode(params)}"


def prepare_appointment(concern_text: str, postal_code: str | None = None) -> AppointmentPlan:
    plz = (postal_code or "").strip()
    plz = plz if POSTAL_CODE.match(plz) else None
    concern = match_concern(concern_text)

    if concern is None:
        query = concern_text.strip()[:120]
        return AppointmentPlan(
            title=query,
            office="Zuständige Behörde – im Bundesportal nach Wohnort auswählen",
            steps=[
                "Öffnen Sie die Suche im Bundesportal und wählen Sie die passende Leistung.",
                "Wählen Sie Ihren Wohnort. Die Seite nennt die zuständige Stelle und, falls vorhanden, die Terminbuchung.",
                "Buchen Sie den Termin auf der Seite der Behörde.",
            ],
            links=[Link(label="Im Bundesportal suchen", url=bundesportal_search_url(query, plz), kind="official_search")],
            notes=[] if plz else ["Mit Ihrer Postleitzahl kann die Suche direkt die zuständige Stelle vorschlagen."],
            alternatives=[{"id": c["id"], "title": c["title"]} for c in concerns()],
        )

    links: list[Link] = []
    if concern.get("bundesportal_url"):
        links.append(Link(label=f"{concern['title']} – Bundesportal", url=concern["bundesportal_url"], kind="official_service"))
    links.append(
        Link(
            label="Zuständige Stelle und Termin für Ihren Ort finden" if plz else "Zuständige Stelle im Bundesportal finden",
            url=bundesportal_search_url(concern["search_query"], plz),
            kind="official_search",
        )
    )
    if concern.get("online_alternative"):
        alt = concern["online_alternative"]
        links.append(Link(label=alt["label"], url=alt["url"], kind="online_service"))
    for law in concern.get("legal", []):
        links.append(Link(label=law["label"], url=law["url"], kind="official_law"))

    steps = [
        f"Zuständig ist: {concern['office']}.",
        "Öffnen Sie den Link für Ihren Ort und wählen Sie dort die Terminbuchung.",
        "Legen Sie die Unterlagen aus der Checkliste bereit.",
    ]
    if concern.get("online_alternative"):
        steps.insert(1, "Prüfen Sie zuerst, ob es online ohne Termin geht.")

    return AppointmentPlan(
        concern_id=concern["id"],
        title=concern["title"],
        office=concern["office"],
        steps=steps,
        bring=list(concern["bring"]),
        links=links,
        notes=list(concern.get("notes", [])) + ([] if plz else ["Mit Ihrer Postleitzahl führt der Link direkt zur Stelle an Ihrem Ort."]),
    )


# --- Amtliche Buchungsseiten ----------------------------------------------------------------------------------
# Eine Terminaktion kann einen Link zur Buchungsseite enthalten, den ein angeschlossener Browser-Agent nach der
# Bestätigung öffnen darf. Damit dieser Agent nie auf Phishing- oder Vermittlerseiten landet, sind nur HTTPS-Adressen
# amtlicher Domains erlaubt. Kommunale Domains sind sehr verschieden; Betreiber ergänzen sie über
# OFFICIAL_BOOKING_DOMAINS (Komma-Liste, z. B. "muenchen.de,stadt-koeln.de").
DEFAULT_OFFICIAL_BOOKING_DOMAINS = (
    "bund.de",  # u. a. verwaltung.bund.de (Bundesportal)
    "baden-wuerttemberg.de", "service-bw.de", "bayern.de", "berlin.de", "brandenburg.de", "bremen.de",
    "hamburg.de", "hessen.de", "mecklenburg-vorpommern.de", "regierung-mv.de", "niedersachsen.de", "nrw.de",
    "rlp.de", "saarland.de", "sachsen.de", "sachsen-anhalt.de", "schleswig-holstein.de", "thueringen.de",
)


class BookingUrlError(ValueError):
    pass


def official_booking_domains() -> tuple[str, ...]:
    extra = [d.strip().lower().lstrip(".") for d in os.getenv("OFFICIAL_BOOKING_DOMAINS", "").split(",") if d.strip()]
    return DEFAULT_OFFICIAL_BOOKING_DOMAINS + tuple(extra)


def validate_booking_url(url: str) -> str:
    """Nur https://-Links auf amtliche Domains (inkl. Subdomains). Gibt die bereinigte URL zurück."""
    url = url.strip()
    parts = urlsplit(url)
    host = (parts.hostname or "").lower().rstrip(".")
    if parts.scheme != "https" or not host or parts.username or parts.password or parts.port not in (None, 443):
        raise BookingUrlError("Die Buchungsseite muss eine https://-Adresse einer Behörde sein.")
    if not any(host == d or host.endswith("." + d) for d in official_booking_domains()):
        raise BookingUrlError(
            f"„{host}“ ist keine freigegebene amtliche Domain. Lassen Sie das Feld leer – der Assistent zeigt dann "
            "die Suche im Bundesportal. Betreiber können weitere Domains über OFFICIAL_BOOKING_DOMAINS zulassen."
        )
    return url
