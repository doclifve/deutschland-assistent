import httpx,pytest
from deutschland_assistent.evidence import EvidenceEngine,GesetzeImInternet,Neuris,Services
from deutschland_assistent.extraction import extract_deadlines,extract_leika_ids,extract_legal_references

def test_exact_reference_and_deadline():
    text="Bitte antworten Sie bis zum 21.10.2026. Rechtsgrundlage ist § 60 SGB I."
    refs=extract_legal_references(text);deadlines=extract_deadlines(text)
    assert refs[0].law=="SGB I"
    assert refs[0].source_url.endswith("/sgb_1/__60.html")
    assert deadlines[0].date.isoformat()=="2026-10-21"

def test_leika_detection():
    assert extract_leika_ids("Leistung 99107066017000")==["99107066017000"]

@pytest.mark.asyncio
async def test_benefit_catalog():
    hits=await Services().search("Wo beantrage ich Kindergeld?",3)
    assert hits and "Kindergeld" in hits[0].title

@pytest.mark.asyncio
async def test_neuris_jsonld():
    def handler(request:httpx.Request):
        assert request.url.path=="/v1/legislation"
        return httpx.Response(200,json={"member":[{"item":{"@id":"/v1/legislation/eli/bund/bgbl-1/1975/s1760","name":"Bürgerliches Gesetzbuch","risAbbreviation":"BGB","legislationIdentifier":"eli/bund/bgbl-1/1975/s1760"},"textMatches":[{"text":"Bürgerliches Gesetzbuch"}]}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        hits=await Neuris(client=client).search("BGB",3)
        assert hits[0].title=="Bürgerliches Gesetzbuch"
        assert hits[0].metadata["beta_dataset"] is True

@pytest.mark.asyncio
async def test_exact_law_ranks_first():
    class EmptyNeuris:
        async def search(self,query,limit=5):return []
    refs=extract_legal_references("§ 60 SGB I")
    bundle=await EvidenceEngine(EmptyNeuris(),GesetzeImInternet(),Services()).collect("§ 60 SGB I",refs,[],5)
    assert bundle.items[0].source_id=="gesetze-im-internet"
    assert bundle.items[0].exact_match is True
