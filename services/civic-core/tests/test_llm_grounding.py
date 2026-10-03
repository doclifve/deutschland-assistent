import json

import httpx
import pytest

from deutschland_assistent.answer_generation import generate_grounded_explanation
from deutschland_assistent.model_provider import (
    GermanyHostedProvider,
    ModelProviderError,
    OpenAICompatibleConfig,
)
from deutschland_assistent.schemas import (
    DocumentAnalysis,
    EvidenceBundle,
    EvidenceItem,
    Requirement,
)


@pytest.mark.asyncio
async def test_grounded_generation_accepts_known_evidence_ids():
    class FakeProvider:
        enabled = True

        async def structured_generate(self, *, system_prompt, user_prompt):
            payload = json.loads(user_prompt)
            ids = {x["id"] for x in payload["evidenz"]}
            assert "document:requirement:0" in ids
            return {
                "claims": [
                    {
                        "text": "Sie sollen Ihren Mietvertrag einreichen.",
                        "evidence_ids": ["document:requirement:0"],
                    }
                ]
            }

    analysis = DocumentAnalysis(
        document_id="doc_test",
        filename="brief.txt",
        document_type="aufforderung",
        text_preview="Bitte reichen Sie Ihren Mietvertrag ein.",
        requirements=[
            Requirement(
                text="Ihren Mietvertrag einreichen",
                kind="document",
                evidence_text="Bitte reichen Sie Ihren Mietvertrag ein.",
            )
        ],
    )
    text = await generate_grounded_explanation(
        FakeProvider(),
        question="Was muss ich tun?",
        analysis=analysis,
        bundle=EvidenceBundle(query="test"),
    )
    assert text == "Sie sollen Ihren Mietvertrag einreichen."


@pytest.mark.asyncio
async def test_grounded_generation_drops_unknown_evidence_id_and_unsupported_date():
    class FakeProvider:
        enabled = True

        async def structured_generate(self, *, system_prompt, user_prompt):
            return {
                "claims": [
                    {
                        "text": "Sie müssen bis zum 31.12.2026 zahlen.",
                        "evidence_ids": ["document:requirement:0"],
                    },
                    {
                        "text": "Das ist sicher rechtswidrig.",
                        "evidence_ids": ["invented:1"],
                    },
                ]
            }

    analysis = DocumentAnalysis(
        document_id="doc_test",
        filename="brief.txt",
        document_type="schreiben",
        text_preview="Bitte zahlen Sie den Betrag.",
        requirements=[
            Requirement(
                text="den Betrag zahlen",
                kind="payment",
                evidence_text="Bitte zahlen Sie den Betrag.",
            )
        ],
    )
    text = await generate_grounded_explanation(
        FakeProvider(),
        question="Was bedeutet das?",
        analysis=analysis,
        bundle=EvidenceBundle(query="test"),
    )
    assert text is None


@pytest.mark.asyncio
async def test_germany_hosted_provider_parses_openai_compatible_json(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")

    def handler(request: httpx.Request):
        assert request.url.path.endswith("/chat/completions")
        body = json.loads(request.content)
        assert body["temperature"] == 0
        assert body["response_format"] == {"type": "json_object"}
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"claims":[{"text":"Test","evidence_ids":["official:0"]}]}'
                        }
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = GermanyHostedProvider(
            OpenAICompatibleConfig(
                base_url="https://llm.example.de/v1",
                model="test-model",
                api_key="secret",
                region="DE",
            ),
            client=client,
        )
        result = await provider.structured_generate(system_prompt="system", user_prompt="user")
        assert result["claims"][0]["text"] == "Test"


def test_germany_hosted_provider_requires_de_region():
    with pytest.raises(ModelProviderError):
        GermanyHostedProvider(
            OpenAICompatibleConfig(
                base_url="https://llm.example.de/v1",
                model="test-model",
                region="EU",
            )
        )


def test_germany_hosted_provider_requires_https_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(ModelProviderError):
        GermanyHostedProvider(
            OpenAICompatibleConfig(
                base_url="http://llm.internal/v1",
                model="test-model",
                region="DE",
            )
        )
