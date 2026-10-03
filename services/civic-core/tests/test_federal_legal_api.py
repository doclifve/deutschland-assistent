import json
from datetime import date

import httpx
import pytest

from deutschland_assistent.evidence import Neuris


@pytest.mark.asyncio
async def test_case_law_search_supports_date_filters_pagination_and_phrase():
    seen = {}

    def handler(request: httpx.Request):
        seen["params"] = dict(request.url.params)
        return httpx.Response(
            200,
            json={
                "member": [
                    {
                        "item": {
                            "@id": "/v1/case-law/KARE123456789",
                            "documentNumber": "KARE123456789",
                            "ecli": "ECLI:DE:BSG:2026:TEST",
                            "headline": "Mitwirkungspflicht",
                            "decisionDate": "2026-04-10",
                            "courtName": "Bundessozialgericht",
                            "documentType": "Urteil",
                        }
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        hits = await Neuris(client=client, cache_ttl_seconds=0).search_case_law(
            "Mitwirkungspflicht",
            3,
            page_index=2,
            date_from=date(2026, 1, 1),
            date_to=date(2026, 9, 30),
            exact_phrase=True,
        )

    assert seen["params"]["searchTerm"] == '"Mitwirkungspflicht"'
    assert seen["params"]["pageIndex"] == "2"
    assert seen["params"]["dateFrom"] == "2026-01-01"
    assert seen["params"]["dateTo"] == "2026-09-30"
    assert hits[0].metadata["ecli"] == "ECLI:DE:BSG:2026:TEST"
    assert hits[0].metadata["html_url"].endswith("/v1/case-law/KARE123456789.html")
    assert hits[0].metadata["xml_url"].endswith("/v1/case-law/KARE123456789.xml")


@pytest.mark.asyncio
async def test_legislation_search_supports_valid_on_and_eli():
    seen = {}

    def handler(request: httpx.Request):
        seen["params"] = dict(request.url.params)
        return httpx.Response(
            200,
            json={
                "member": [
                    {
                        "item": {
                            "@id": "/v1/legislation/eli/bund/bgbl-1/1975/s1760/2026-01-01/1/deu",
                            "name": "Beispielgesetz",
                            "legislationIdentifier": "TEST-1",
                        }
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        hits = await Neuris(client=client, cache_ttl_seconds=0).search_legislation(
            "Beispielgesetz",
            2,
            valid_on=date(2026, 5, 1),
            exact_phrase=True,
        )

    assert seen["params"]["searchTerm"] == '"Beispielgesetz"'
    assert seen["params"]["temporalCoverageFrom"] == "2026-05-01"
    assert seen["params"]["temporalCoverageTo"] == "2026-05-01"
    assert hits[0].metadata["eli"].startswith("eli/bund/")


@pytest.mark.asyncio
async def test_api_cache_avoids_duplicate_request():
    calls = 0

    def handler(request: httpx.Request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={"member": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        api = Neuris(client=client, cache_ttl_seconds=60)
        await api.search_case_law("Test", 1)
        await api.search_case_law("Test", 1)

    assert calls == 1


@pytest.mark.asyncio
async def test_api_retries_429_then_succeeds():
    calls = 0

    def handler(request: httpx.Request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"member": []})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        api = Neuris(client=client, max_retries=1, cache_ttl_seconds=0)
        await api.search_case_law("Test", 1)

    assert calls == 2


@pytest.mark.asyncio
async def test_complete_case_law_detail_enrichment():
    def handler(request: httpx.Request):
        if request.url.path == "/v1/case-law":
            return httpx.Response(
                200,
                json={
                    "member": [
                        {
                            "item": {
                                "@id": "/v1/case-law/KARE123456789",
                                "documentNumber": "KARE123456789",
                                "ecli": "ECLI:DE:BSG:2026:ABC",
                                "headline": "Mitwirkung",
                                "decisionDate": "2026-02-02",
                                "courtName": "Bundessozialgericht",
                            }
                        }
                    ]
                },
            )
        if request.url.path == "/v1/case-law/KARE123456789":
            return httpx.Response(
                200,
                json={
                    "documentNumber": "KARE123456789",
                    "ecli": "ECLI:DE:BSG:2026:ABC",
                    "decisionDate": "2026-02-02",
                    "guidingPrinciple": "Eine konkrete amtliche Leitsatz-Passage.",
                    "decisionGrounds": "Weitere Entscheidungsgründe.",
                },
            )
        raise AssertionError(request.url.path)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        api = Neuris(client=client, cache_ttl_seconds=0)
        hits = await api.search_case_law("Mitwirkung", 1)
        enriched = await api.enrich_case_law_hits(hits, max_documents=1)

    assert "Leitsatz:" in enriched[0].snippet
    assert "amtliche Leitsatz-Passage" in enriched[0].snippet
    assert enriched[0].metadata["content_source"] == "detail-json"


def test_case_law_format_url_rejects_invalid_format():
    api = Neuris()
    with pytest.raises(ValueError):
        api.case_law_format_url("KARE123456789", "pdf")
