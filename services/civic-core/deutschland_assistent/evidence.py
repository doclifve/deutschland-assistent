from __future__ import annotations

import asyncio
import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

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
    source_id = "neuris"

    def __init__(
        self,
        base_url: str = "https://testphase.rechtsinformationen.bund.de",
        client: httpx.AsyncClient | None = None,
        timeout: float = 8.0,
    ):
        self.base_url = base_url.rstrip("/") + "/"
        self.client = client
        self.timeout = timeout

    async def _get(self, path: str, params: dict):
        if self.client:
            r = await self.client.get(urljoin(self.base_url, path.lstrip("/")), params=params)
            r.raise_for_status()
            return r.json()
        async with httpx.AsyncClient(
            timeout=self.timeout,
            headers={"User-Agent": "Deutschland-Assistent/0.2.1"},
        ) as c:
            r = await c.get(urljoin(self.base_url, path.lstrip("/")), params=params)
            r.raise_for_status()
            return r.json()

    async def search_legislation(self, query: str, limit: int = 5) -> list[EvidenceItem]:
        today = date.today().isoformat()
        payload = await self._get(
            "/v1/legislation",
            {
                "searchTerm": query,
                "temporalCoverageFrom": today,
                "temporalCoverageTo": today,
                "size": min(max(limit, 1), 20),
                "pageIndex": 0,
            },
        )
        members = payload.get("member") or payload.get("hydra:member") or []
        out: list[EvidenceItem] = []
        for rank, member in enumerate(members[:limit]):
            entry = member.get("item", member) if isinstance(member, dict) else {}
            if not isinstance(entry, dict):
                continue
            title = entry.get("name") or entry.get("headline") or entry.get("risAbbreviation") or "Bundesrecht"
            ident = entry.get("legislationIdentifier") or entry.get("@id") or ""
            rid = str(entry.get("@id") or ident or title)
            url = urljoin(self.base_url, rid.lstrip("/")) if rid else self.base_url
            matches = member.get("textMatches", []) if isinstance(member, dict) else []
            snippets = []
            for match in matches[:3]:
                if isinstance(match, dict):
                    value = match.get("text") or match.get("highlightedText") or match.get("value")
                    if value:
                        snippets.append(str(value))
            stable = hashlib.sha1(rid.encode("utf-8", errors="ignore")).hexdigest()[:12]
            out.append(
                EvidenceItem(
                    id=f"neuris-law:{stable}",
                    source_id=self.source_id,
                    kind="official_legal_api",
                    authority="Bundesministerium der Justiz / Bundesamt für Justiz",
                    title=str(title),
                    url=url,
                    locator=str(ident) if ident else None,
                    snippet=" ".join(snippets)[:900] or None,
                    score=max(0.72, 0.96 - rank * 0.035),
                    metadata={
                        "ris_abbreviation": entry.get("risAbbreviation"),
                        "legislation_identifier": ident,
                        "beta_dataset": True,
                    },
                )
            )
        return out

    async def search_case_law(self, query: str, limit: int = 5) -> list[EvidenceItem]:
        payload = await self._get(
            "/v1/case-law",
            {"searchTerm": query, "size": min(max(limit, 1), 20), "pageIndex": 0},
        )
        members = payload.get("member") or payload.get("hydra:member") or []
        out: list[EvidenceItem] = []
        for rank, member in enumerate(members[:limit]):
            entry = member.get("item", member) if isinstance(member, dict) else {}
            if not isinstance(entry, dict):
                continue
            document_number = str(entry.get("documentNumber") or "")
            ecli = str(entry.get("ecli") or "")
            title = (
                entry.get("headline")
                or entry.get("titleLine")
                or (entry.get("decisionName") or [None])[0]
                or "Gerichtsentscheidung"
            )
            court = entry.get("courtName") or entry.get("courtType") or "Bundesrechtsprechung"
            decision_date = entry.get("decisionDate")
            rid = str(entry.get("@id") or (f"/v1/case-law/{document_number}" if document_number else ""))
            url = urljoin(self.base_url, rid.lstrip("/")) if rid else self.base_url
            matches = member.get("textMatches", []) if isinstance(member, dict) else []
            snippets = []
            for match in matches[:3]:
                if isinstance(match, dict) and match.get("text"):
                    snippets.append(str(match["text"]))
            stable_seed = document_number or ecli or rid or str(title)
            stable = hashlib.sha1(stable_seed.encode("utf-8", errors="ignore")).hexdigest()[:12]
            locator_parts = [x for x in [str(court), decision_date, ecli or document_number] if x]
            out.append(
                EvidenceItem(
                    id=f"neuris-case:{stable}",
                    source_id=self.source_id,
                    kind="official_case_law",
                    authority=str(court),
                    title=str(title),
                    url=url,
                    locator=" · ".join(locator_parts) or None,
                    snippet=" ".join(snippets)[:900] or entry.get("outline") or None,
                    score=max(0.62, 0.86 - rank * 0.035),
                    metadata={
                        "document_number": document_number,
                        "ecli": ecli,
                        "decision_date": decision_date,
                        "court": str(court),
                        "document_type": entry.get("documentType"),
                        "beta_dataset": True,
                    },
                )
            )
        return out

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
        tokens = {x for x in self._tokens(query) if len(x) > 2 and x not in {"ich", "sie", "wir", "wie", "was", "wo", "der", "die", "das", "und", "oder", "für", "mit"}}
        query_norm = " ".join(self._tokens(query))
        scored = []
        for item in self.services:
            hay_text = " ".join(
                [str(item.get("title", "")), str(item.get("summary", "")), " ".join(item.get("keywords", []))]
            )
            hay_tokens = self._tokens(hay_text)
            overlap = len(tokens & hay_tokens)
            phrase_bonus = sum(2 for keyword in item.get("keywords", []) if str(keyword).lower() in query_norm)
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
        return set("".join(ch.lower() if ch.isalnum() or ch in "äöüß" else " " for ch in text).split())


class EvidenceEngine:
    def __init__(self, neuris=None, gii=None, services=None):
        self.neuris = neuris or Neuris()
        self.gii = gii or GesetzeImInternet()
        self.services = services or Services()

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
        items = [self.gii.resolve(r) for r in refs] + [self.services.from_leika(x) for x in leika]
        warnings: list[str] = []
        legal_query = self._legal_query(query, refs)
        service_task = asyncio.create_task(self.services.search(query, min(5, limit)))
        legislation_task = asyncio.create_task(self.neuris.search_legislation(legal_query, min(5, limit)))
        case_task = None
        if include_case_law and self._looks_legal(query, refs):
            case_task = asyncio.create_task(self.neuris.search_case_law(legal_query, min(4, limit)))

        try:
            items.extend(await service_task)
        except Exception as exc:
            warnings.append(f"Leistungsregister nicht verfügbar: {type(exc).__name__}")
        try:
            items.extend(await legislation_task)
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            warnings.append(
                f"NeuRIS-Gesetzessuche nicht verfügbar; direkter Gesetzes-Fallback bleibt aktiv. ({type(exc).__name__})"
            )
        if case_task:
            try:
                items.extend(await case_task)
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                warnings.append(f"NeuRIS-Rechtsprechung nicht verfügbar. ({type(exc).__name__})")

        best: dict[str, EvidenceItem] = {}
        for item in items:
            key = (item.url or item.id).rstrip("/")
            if key not in best or item.score > best[key].score:
                best[key] = item
        ranked = list(best.values())
        ranked.sort(key=lambda x: (x.exact_match, x.score), reverse=True)
        if refs and not any(i.kind == "official_legal_api" for i in ranked):
            warnings.append(
                "NeuRIS ist ein Testdienst mit unvollständigem Datenbestand; Gesetze-im-Internet-Fallback aktiv."
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
