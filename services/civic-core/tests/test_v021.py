import httpx
import pytest
from deutschland_assistent.evidence import EvidenceEngine, GesetzeImInternet, Neuris, Services
from deutschland_assistent.extraction import extract_appeal_instruction, extract_deadlines, extract_legal_references, extract_requirements

def test_requirements_and_deadline_from_authority_letter():
 text="""Jobcenter Hamburg
Aufforderung zur Mitwirkung
Bitte reichen Sie Kontoauszüge der letzten drei Monate ein.
Bitte legen Sie Ihren Mietvertrag vor.
Antworten Sie bitte bis zum 21.10.2026.
Rechtsgrundlage: § 60 SGB I."""
 requirements=extract_requirements(text)
 assert any("Kontoauszüge" in r.text and r.kind=="document" for r in requirements)
 assert any("Mietvertrag" in r.text for r in requirements)
 assert extract_deadlines(text)[0].date.isoformat()=="2026-10-21"
 assert extract_legal_references(text)[0].law=="SGB I"

def test_appeal_instruction_widerspruch():
 text="""Rechtsbehelfsbelehrung
Gegen diesen Bescheid kann innerhalb eines Monats nach Bekanntgabe Widerspruch
bei dem Jobcenter Hamburg schriftlich, elektronisch oder zur Niederschrift eingelegt werden."""
 appeal=extract_appeal_instruction(text)
 assert appeal and appeal.remedy=="widerspruch"; assert "innerhalb eines Monats" in (appeal.deadline_expression or "")
 assert "schriftlich" in appeal.methods and "elektronisch" in appeal.methods and appeal.confidence=="high"

def test_appeal_instruction_klage_without_heading():
 appeal=extract_appeal_instruction("Gegen den Bescheid kann innerhalb eines Monats nach Zustellung Klage beim Sozialgericht Berlin erhoben werden.")
 assert appeal and appeal.remedy=="klage"

@pytest.mark.asyncio
async def test_neuris_case_law_jsonld():
 def handler(request:httpx.Request):
  assert request.url.path=="/v1/case-law"
  return httpx.Response(200,json={"member":[{"item":{"@id":"/v1/case-law/KARE123","documentNumber":"KARE123","ecli":"ECLI:DE:BSG:2026:TEST","headline":"Mitwirkungspflicht und Leistungsentzug","decisionDate":"2026-04-10","courtName":"Bundessozialgericht","documentType":"Urteil"},"textMatches":[{"text":"Mitwirkungspflicht"}]}]})
 async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
  hits=await Neuris(client=client).search_case_law("Mitwirkungspflicht",3)
  assert hits[0].kind=="official_case_law" and hits[0].authority=="Bundessozialgericht"
  assert hits[0].metadata["ecli"]=="ECLI:DE:BSG:2026:TEST"

@pytest.mark.asyncio
async def test_evidence_engine_adds_case_law_for_legal_query():
 class FakeNeuris:
  async def search_legislation(self,query,limit=5): return []
  async def search_case_law(self,query,limit=5):
   from deutschland_assistent.schemas import EvidenceItem
   return [EvidenceItem(id="case:1",source_id="neuris",kind="official_case_law",authority="BSG",title="Testentscheidung",score=0.8)]
 refs=extract_legal_references("§ 60 SGB I")
 bundle=await EvidenceEngine(FakeNeuris(),GesetzeImInternet(),Services()).collect("Widerspruch gegen Bescheid § 60 SGB I",refs,[],8,include_case_law=True)
 assert bundle.items[0].source_id=="gesetze-im-internet"; assert any(i.kind=="official_case_law" for i in bundle.items)
