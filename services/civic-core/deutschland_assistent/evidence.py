from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import time
from datetime import date
from pathlib import Path
from urllib.parse import quote, urljoin

import httpx

from .schemas import EvidenceBundle, EvidenceItem, LegalReference


class GesetzeImInternet:
    source_id = "gesetze-im-internet"

    def resolve(self, ref: LegalReference) -> EvidenceItem:
        stable = hashlib.sha1(f"{ref.law}:{ref.section}".encode()).hexdigest()[:12]
        return EvidenceItem(
            id=f"gii:{stable}",
            source_id=self.source_id,
            kind="official_law",
            authority="Bundesministerium der Justiz / Bundesamt für Justiz",
            title=f"{ref.section} {ref.law}",
            url=ref.source_url,
            locator=ref.section,
            snippet=f"Amtliche Online-Fassung des erkannten Gesetzeszitats {ref.raw}.",
            score=1.0,
            exact_match=True,
            metadata={"law": ref.law, "section": ref.section},
        )


class Neuris:
    """Connector for the official Rechtsinformationen-des-Bundes API.

    The public service is still a test-phase API. The connector therefore keeps
    exact-law fallbacks, uses short-lived caching, retries transient failures,
    and exposes canonical ELI/ECLI metadata without treating search results as
    legal conclusions.
    """

    source_id = "neuris"

    def __init__(
        self,
        base_url: str | None = None,
        client: httpx.AsyncClient | None = None,
        timeout: float | None = None,
        cache_ttl_seconds: int | None = None,
        max_retries: int | None = None,
    ):
        self.base_url = (
            base_url
            or os.getenv("NEURIS_BASE_URL", "https://testphase.rechtsinformationen.bund.de")
        ).rstrip("/") + "/"
        self.client = client
        self.timeout = timeout or float(os.getenv("NEURIS_TIMEOUT_SECONDS", "8"))
        self.cache_ttl_seconds = (
            cache_ttl_seconds
            if cache_ttl_seconds is not None
            else int(os.getenv("NEURIS_CACHE_TTL_SECONDS", "900"))
        )
        self.max_retries = (
            max_retries
            if max_retries is not None
            else int(os.getenv("NEURIS_MAX_RETRIES", "2"))
        )
        self._cache: dict[str, tuple[float, object]] = {}

    def _cache_key(self, path: str, params: dict | None) -> str:
        return json.dumps(
            [path, sorted((params or {}).items())],
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )

    def _cache_get(self, key: str):
        entry = self._cache.get(key)
        if not entry:
            return None
        created, payload = entry
        if time.monotonic() - created > self.cache_ttl_seconds:
            self._cache.pop(key, None)
            return None
        return payload

    def _cache_put(self, key: str, payload: object) -> None:
        if self.cache_ttl_seconds <= 0:
            return
        self._cache[key] = (time.monotonic(), payload)
        if len(self._cache) > 512:
            oldest = min(self._cache, key=lambda k: self._cache[k][0])
            self._cache.pop(oldest, None)

    async def _request(self, path: str, params: dict | None = None) -> httpx.Response:
        url = urljoin(self.base_url, path.lstrip("/"))
        headers = {
            "User-Agent": "Deutschland-Assistent/0.2.4",
            "Accept": "application/json",
        }

        for attempt in range(self.max_retries + 1):
            try:
                if self.client:
                    response = await self.client.get(url, params=params, headers=headers)
                else:
                    async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
                        response = await client.get(url, params=params)

                if response.status_code == 429 or 500 <= response.status_code < 600:
                    if attempt >= self.max_retries:
                        response.raise_for_status()
                    retry_after = response.headers.get("Retry-After")
                    try:
                        delay = float(retry_after) if retry_after else 0.25 * (2**attempt)
                    except ValueError:
                        delay = 0.25 * (2**attempt)
                    await asyncio.sleep(min(delay, 4.0))
                    continue

                response.raise_for_status()
                return response
            except httpx.HTTPError:
                if attempt >= self.max_retries:
                    raise
                await asyncio.sleep(min(0.25 * (2**attempt), 4.0))

        raise httpx.HTTPError("Rechtsinformationen-des-Bundes API request failed")

    async def _get_json(self, path: str, params: dict | None = None):
        key = self._cache_key(path, params)
        cached = self._cache_get(key)
        if cached is not None:
            return cached
        response = await self._request(path, params)
        payload = response.json()
        self._cache_put(key, payload)
        return payload

    @staticmethod
    def _search_term(query: str, exact_phrase: bool) -> str:
        clean = " ".join(query.split())
        if exact_phrase and clean and not (clean.startswith('"') and clean.endswith('"')):
            return f'"{clean}"'
        return clean

    async def search_legislation(
        self,
        query: str,
        limit: int = 5,
        *,
        page_index: int = 0,
        valid_on: date | None = None,
        exact_phrase: bool = False,
    ) -> list[EvidenceItem]:
        day = (valid_on or date.today()).isoformat()
        payload = await self._get_json(
            "/v1/legislation",
            {
                "searchTerm": self._search_term(query, exact_phrase),
                "temporalCoverageFrom": day,
                "temporalCoverageTo": day,
                "size": min(max(limit, 1), 20),
                "pageIndex": max(page_index, 0),
            },
        )
        members = payload.get("member") or payload.get("hydra:member") or []
        out: list[EvidenceItem] = []
        for rank, member in enumerate(members[:limit]):
            entry = member.get("item", member) if isinstance(member, dict) else {}
            if not isinstance(entry, dict):
                continue
            title = (
                entry.get("name")
                or entry.get("headline")
                or entry.get("risAbbreviation")
                or "Bundesrecht"
            )
            ident = entry.get("legislationIdentifier") or ""
            rid = str(entry.get("@id") or "")
            url = urljoin(self.base_url, rid.lstrip("/")) if rid else self.base_url
            eli = _extract_eli(rid, entry)
            matches = member.get("textMatches", []) if isinstance(member, dict) else []
            snippets = []
            for match in matches[:3]:
                if isinstance(match, dict):
                    value = match.get("text") or match.get("highlightedText") or match.get("value")
                    if value:
                        snippets.append(str(value))
            stable_seed = rid or str(ident) or str(title)
            stable = hashlib.sha1(stable_seed.encode("utf-8", errors="ignore")).hexdigest()[:12]
            metadata = {
                "ris_abbreviation": entry.get("risAbbreviation"),
                "legislation_identifier": ident,
                "eli": eli,
                "valid_on": day,
                "page_index": page_index,
                "beta_dataset": True,
            }
            out.append(
                EvidenceItem(
                    id=f"neuris-law:{stable}",
                    source_id=self.source_id,
                    kind="official_legal_api",
                    authority="Bundesministerium der Justiz / Bundesamt für Justiz",
                    title=str(title),
                    url=url,
                    locator=str(ident or eli) if (ident or eli) else None,
                    snippet=" ".join(snippets)[:1200] or None,
                    score=max(0.72, 0.96 - rank * 0.035),
                    metadata={k: v for k, v in metadata.items() if v not in (None, "")},
                )
            )
        return out

    async def search_case_law(
        self,
        query: str,
        limit: int = 5,
        *,
        page_index: int = 0,
        date_from: date | None = None,
        date_to: date | None = None,
        exact_phrase: bool = False,
    ) -> list[EvidenceItem]:
        params: dict[str, object] = {
            "searchTerm": self._search_term(query, exact_phrase),
            "size": min(max(limit, 1), 20),
            "pageIndex": max(page_index, 0),
        }
        if date_from:
            params["dateFrom"] = date_from.isoformat()
        if date_to:
            params["dateTo"] = date_to.isoformat()

        payload = await self._get_json("/v1/case-law", params)
        members = payload.get("member") or payload.get("hydra:member") or []
        out: list[EvidenceItem] = []
        for rank, member in enumerate(members[:limit]):
            entry = member.get("item", member) if isinstance(member, dict) else {}
            if not isinstance(entry, dict):
                continue
            document_number = str(entry.get("documentNumber") or "")
            ecli = str(entry.get("ecli") or "")
            decision_names = entry.get("decisionName")
            decision_name = decision_names[0] if isinstance(decision_names, list) and decision_names else None
            title = (
                entry.get("headline")
                or entry.get("titleLine")
                or decision_name
                or "Gerichtsentscheidung"
            )
            court = entry.get("courtName") or entry.get("courtType") or "Bundesrechtsprechung"
            decision_date = entry.get("decisionDate")
            rid = str(
                entry.get("@id")
                or (f"/v1/case-law/{document_number}" if document_number else "")
            )
            url = urljoin(self.base_url, rid.lstrip("/")) if rid else self.base_url
            matches = member.get("textMatches", []) if isinstance(member, dict) else []
            snippets = []
            for match in matches[:3]:
                if isinstance(match, dict):
                    value = match.get("text") or match.get("highlightedText") or match.get("value")
                    if value:
                        snippets.append(str(value))

            stable_seed = document_number or ecli or rid or str(title)
            stable = hashlib.sha1(stable_seed.encode("utf-8", errors="ignore")).hexdigest()[:12]
            locator_parts = [x for x in [str(court), decision_date, ecli or document_number] if x]
            metadata = {
                "document_number": document_number,
                "ecli": ecli,
                "decision_date": decision_date,
                "court": str(court),
                "document_type": entry.get("documentType"),
                "page_index": page_index,
                "json_url": self.case_law_format_url(document_number, "json") if document_number else None,
                "html_url": self.case_law_format_url(document_number, "html") if document_number else None,
                "xml_url": self.case_law_format_url(document_number, "xml") if document_number else None,
                "beta_dataset": True,
            }
            out.append(
                EvidenceItem(
                    id=f"neuris-case:{stable}",
                    source_id=self.source_id,
                    kind="official_case_law",
                    authority=str(court),
                    title=str(title),
                    url=url,
                    locator=" · ".join(locator_parts) or None,
                    snippet=" ".join(snippets)[:1200] or entry.get("outline") or None,
                    score=max(0.62, 0.86 - rank * 0.035),
                    metadata={k: v for k, v in metadata.items() if v not in (None, "")},
                )
            )
        return out

    async def get_case_law(self, document_number: str) -> dict:
        """Fetch complete JSON metadata/text fields for one official decision."""
        if not re.fullmatch(r"[A-Za-z0-9:._-]{4,160}", document_number):
            raise ValueError("Ungültige Dokumentnummer.")
        payload = await self._get_json(f"/v1/case-law/{quote(document_number, safe=':._-')}")
        if not isinstance(payload, dict):
            raise ValueError("Unerwartetes Rechtsprechungsformat.")
        return payload

    def case_law_format_url(self, document_number: str, format: str = "json") -> str:
        if not re.fullmatch(r"[A-Za-z0-9:._-]{4,160}", document_number):
            raise ValueError("Ungültige Dokumentnummer.")
        encoded = quote(document_number, safe=":._-")
        suffix = "" if format == "json" else f".{format}"
        if format not in {"json", "html", "xml"}:
            raise ValueError("Format muss json, html oder xml sein.")
        return urljoin(self.base_url, f"v1/case-law/{encoded}{suffix}")

    async def enrich_case_law_hits(
        self,
        hits: list[EvidenceItem],
        *,
        max_documents: int = 2,
    ) -> list[EvidenceItem]:
        """Enrich top search hits with fields from the complete decision endpoint."""
        candidates = [
            h
            for h in hits[:max_documents]
            if h.kind == "official_case_law" and h.metadata.get("document_number")
        ]
        if not candidates:
            return hits

        async def enrich(hit: EvidenceItem) -> None:
            document_number = str(hit.metadata["document_number"])
            try:
                detail = await self.get_case_law(document_number)
            except (httpx.HTTPError, ValueError, TypeError):
                return
            snippet = _case_law_detail_snippet(detail)
            if snippet:
                hit.snippet = snippet[:1800]
                hit.metadata["content_source"] = "detail-json"
            if detail.get("ecli"):
                hit.metadata["ecli"] = str(detail["ecli"])
            if detail.get("decisionDate"):
                hit.metadata["decision_date"] = str(detail["decisionDate"])

        await asyncio.gather(*(enrich(hit) for hit in candidates))
        return hits

    async def search(self, query: str, limit: int = 5) -> list[EvidenceItem]:
        return await self.search_legislation(query, limit)


class Services:
    source_id = "bundesportal"

    def __init__(self):
        path = Path(__file__).resolve().parent / "data" / "services.de.json"
        self.services = json.loads(path.read_text(encoding="utf-8"))

    def from_leika(self, leika_id: str) -> EvidenceItem:
        return EvidenceItem(
            id=f"bundesportal:leika:{leika_id}",
            source_id=self.source_id,
            kind="official_service",
            authority="Bundesportal",
            title=f"Verwaltungsleistung (LeiKa {leika_id})",
            url=f"https://verwaltung.bund.de/leistungsverzeichnis/DE/leistung/{leika_id}",
            locator=f"LeiKa {leika_id}",
            snippet="Offizielle Leistungsseite im Bundesportal; regionale Angaben können abweichen.",
            score=0.97,
            exact_match=True,
            metadata={"leika_id": leika_id},
        )

    async def search(self, query: str, limit: int = 5) -> list[EvidenceItem]:
        tokens = {
            x
            for x in self._tokens(query)
            if len(x) > 2
            and x not in {"ich", "sie", "wir", "wie", "was", "wo", "der", "die", "das", "und", "oder", "für", "mit"}
        }
        query_norm = " ".join(self._tokens(query))
        scored = []
        for item in self.services:
            hay_text = " ".join(
                [
                    str(item.get("title", "")),
                    str(item.get("summary", "")),
                    " ".join(item.get("keywords", [])),
                ]
            )
            hay_tokens = self._tokens(hay_text)
            overlap = len(tokens & hay_tokens)
            phrase_bonus = sum(
                2
                for keyword in item.get("keywords", [])
                if str(keyword).lower() in query_norm
            )
            total = overlap + phrase_bonus
            if total:
                scored.append((min(0.95, 0.72 + 0.06 * total), item))
        scored.sort(key=lambda x: x[0], reverse=True)
        out: list[EvidenceItem] = []
        for score, item in scored[:limit]:
            url = str(item["url"])
            stable = hashlib.sha1(url.encode()).hexdigest()[:12]
            out.append(
                EvidenceItem(
                    id=f"service:{stable}",
                    source_id=self.source_id,
                    kind="official_service",
                    authority=str(item.get("authority", "Bundesportal / Bundesbehörde")),
                    title=str(item["title"]),
                    url=url,
                    snippet=str(item.get("summary") or ""),
                    score=score,
                )
            )
        return out

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return set(
            "".join(
                ch.lower() if ch.isalnum() or ch in "äöüß" else " " for ch in text
            ).split()
        )


class EvidenceEngine:
    def __init__(self, neuris=None, gii=None, services=None):
        self.neuris = neuris or Neuris()
        self.gii = gii or GesetzeImInternet()
        self.services = services or Services()
        self.enrich_case_law = os.getenv("NEURIS_ENRICH_CASE_LAW", "true").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    async def collect(
        self,
        query: str,
        legal_refs: list[LegalReference] | None = None,
        leika_ids: list[str] | None = None,
        limit: int = 8,
        include_case_law: bool = True,
    ) -> EvidenceBundle:
        refs = legal_refs or []
        leika = leika_ids or []
        items = [self.gii.resolve(r) for r in refs] + [
            self.services.from_leika(x) for x in leika
        ]
        warnings: list[str] = []
        legal_query = self._legal_query(query, refs)
        service_task = asyncio.create_task(self.services.search(query, min(5, limit)))
        legislation_task = asyncio.create_task(
            self.neuris.search_legislation(legal_query, min(5, limit))
        )
        case_task = None
        if include_case_law and self._looks_legal(query, refs):
            case_task = asyncio.create_task(
                self.neuris.search_case_law(legal_query, min(4, limit))
            )

        try:
            items.extend(await service_task)
        except Exception as exc:
            warnings.append(f"Leistungsregister nicht verfügbar: {type(exc).__name__}")
        try:
            items.extend(await legislation_task)
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            warnings.append(
                "Rechtsinformationen-des-Bundes-Gesetzessuche nicht verfügbar; "
                f"direkter Gesetzes-Fallback bleibt aktiv. ({type(exc).__name__})"
            )
        if case_task:
            try:
                case_hits = await case_task
                if self.enrich_case_law and isinstance(self.neuris, Neuris):
                    case_hits = await self.neuris.enrich_case_law_hits(case_hits)
                items.extend(case_hits)
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                warnings.append(
                    f"Rechtsinformationen-des-Bundes-Rechtsprechung nicht verfügbar. ({type(exc).__name__})"
                )

        best: dict[str, EvidenceItem] = {}
        for item in items:
            key = (item.url or item.id).rstrip("/")
            if key not in best or item.score > best[key].score:
                best[key] = item
        ranked = list(best.values())
        ranked.sort(key=lambda x: (x.exact_match, x.score), reverse=True)
        if refs and not any(i.kind == "official_legal_api" for i in ranked):
            warnings.append(
                "Rechtsinformationen des Bundes befinden sich in der Testphase; "
                "Gesetze-im-Internet-Fallback aktiv."
            )
        return EvidenceBundle(query=query, items=ranked[:limit], warnings=warnings)

    @staticmethod
    def _legal_query(query: str, refs: list[LegalReference]) -> str:
        if refs:
            return " ".join(dict.fromkeys(f"{r.section} {r.law}" for r in refs))
        return " ".join(re.findall(r"[A-Za-zÄÖÜäöüß0-9§-]+", query)[:18])

    @staticmethod
    def _looks_legal(query: str, refs: list[LegalReference]) -> bool:
        if refs:
            return True
        return bool(
            re.search(
                r"\b(widerspruch|einspruch|klage|beschwerde|urteil|beschluss|rechtsprechung|rechtmäßig|gesetz|§|bescheid)\b",
                query,
                re.I,
            )
        )


def _extract_eli(rid: str, entry: dict) -> str | None:
    for candidate in (
        entry.get("eli"),
        entry.get("legislationIdentifier"),
        rid,
    ):
        if not candidate:
            continue
        match = re.search(r"(eli/bund/[^?#\s]+)", str(candidate))
        if match:
            return match.group(1)
    return None


def _case_law_detail_snippet(detail: dict) -> str | None:
    """Prefer compact legally useful text fields from the official detail response."""
    fields = (
        ("Leitsatz", detail.get("guidingPrinciple")),
        ("Orientierungssatz", detail.get("headnote")),
        ("Überschrift", detail.get("headline")),
        ("Tenor", detail.get("tenor")),
        ("Entscheidungsgründe", detail.get("decisionGrounds")),
        ("Gründe", detail.get("grounds")),
        ("Tatbestand", detail.get("caseFacts")),
        ("Langtext", detail.get("otherLongText")),
    )
    parts: list[str] = []
    remaining = 1800
    for label, value in fields:
        if not value:
            continue
        clean = " ".join(str(value).split())
        if not clean:
            continue
        piece = f"{label}: {clean}"
        if len(piece) > remaining:
            piece = piece[:remaining].rstrip()
        parts.append(piece)
        remaining -= len(piece) + 1
        if remaining <= 80:
            break
    return " ".join(parts) if parts else None
