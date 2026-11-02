"""Terminaktionen: nur amtliche Buchungsseiten, klarer nächster Schritt statt Scheinbuchung."""
import pytest
from fastapi.testclient import TestClient

from deutschland_assistent.appointments import BookingUrlError, validate_booking_url
from deutschland_assistent.main import app

client = TestClient(app)


@pytest.mark.parametrize(
    "url",
    [
        "https://service.berlin.de/dienstleistung/120703/",
        "https://verwaltung.bund.de/leistungsverzeichnis/DE/leistung/99107066017000",
        "https://www.service-bw.de/zufi/leistungen/",
        "https://berlin.de/",
    ],
)
def test_official_domains_accepted(url):
    assert validate_booking_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "https://beliebige-fremde-seite.example/",
        "http://service.berlin.de/",  # kein HTTPS
        "https://evilberlin.de/",  # Endung ohne Punkt-Grenze
        "https://service.berlin.de.evil.com/",  # amtlicher Name als Subdomain einer fremden Domain
        "https://user@evil.com/",
        "https://service.berlin.de@evil.com/",  # Userinfo-Trick
        "https://service.berlin.de:8443/",
        "https://93.184.216.34/",
        "javascript:alert(1)",
        "",
    ],
)
def test_untrusted_urls_rejected(url):
    with pytest.raises(BookingUrlError):
        validate_booking_url(url)


def test_operator_can_allow_municipal_domains(monkeypatch):
    with pytest.raises(BookingUrlError):
        validate_booking_url("https://stadt.muenchen.de/terminvereinbarung.html")
    monkeypatch.setenv("OFFICIAL_BOOKING_DOMAINS", "muenchen.de, stadt-koeln.de")
    assert validate_booking_url("https://stadt.muenchen.de/terminvereinbarung.html")


def test_api_rejects_foreign_booking_url():
    r = client.post("/v1/actions/appointment", json={"service": "Test", "official_booking_url": "https://fremd.example/"})
    assert r.status_code == 422
    assert "keine freigegebene amtliche Domain" in r.json()["detail"]


def test_booking_link_with_official_url():
    url = "https://service.berlin.de/dienstleistung/120703/"
    action = client.post("/v1/actions/appointment", json={"service": "Personalausweis", "official_booking_url": url}).json()
    assert action["payload"]["booking_link"] == url
    assert action["execution_target"] == "openclaw_browser"


def test_booking_link_falls_back_to_bundesportal_search():
    action = client.post("/v1/actions/appointment", json={"service": "Personalausweis beantragen", "location": "Berlin"}).json()
    assert action["payload"]["booking_link"].startswith("https://verwaltung.bund.de/leistungsverzeichnis/de/suche?")
    assert "Personalausweis" in action["payload"]["booking_link"]
    approved = client.post(f"/v1/actions/{action['action_id']}/confirm", json={"approve": True, "expected_version": 1}).json()
    assert approved["status"] == "approved"
    assert approved["payload"]["booking_link"] == action["payload"]["booking_link"]
