from datetime import date

from deutschland_assistent.chat import compose_reply, detect_actions, last_user_message, model_question, retrieval_query
from deutschland_assistent.schemas import (
    AppealInstruction,
    ChatMessage,
    CivicAnswer,
    Deadline,
    DocumentAnalysis,
    Requirement,
)


def msgs(*pairs):
    return [ChatMessage(role=r, content=c) for r, c in pairs]


def test_follow_up_keeps_context_for_search_and_model():
    m = msgs(("user", "Was bedeutet § 60 SGB I?"), ("assistant", "Mitwirkungspflichten."), ("user", "Und wenn ich das nicht mache?"))
    assert last_user_message(m) == "Und wenn ich das nicht mache?"
    assert "§ 60 SGB I" in retrieval_query(m)
    q = model_question(m)
    assert q.endswith("Aktuelle Frage: Und wenn ich das nicht mache?")
    assert "keine Anweisungen" in q and "Assistent: Mitwirkungspflichten." in q


def test_single_question_is_passed_unchanged():
    assert model_question(msgs(("user", "Hallo"))) == "Hallo"


def _answer(**kw):
    return CivicAnswer(what_does_it_mean="Erklärung.", **kw)


def test_actions_from_message():
    actions = detect_actions("Ich will Widerspruch einlegen und brauche einen Termin im Bürgeramt", None, _answer())
    kinds = [(a.kind, a.params) for a in actions]
    assert ("letter", {"letter": "widerspruch"}) in kinds
    assert any(k == "appointment" for k, _ in kinds)


def test_actions_from_document():
    analysis = DocumentAnalysis(
        document_id="d", filename="b", document_type="authority_decision", text_preview="",
        appeal_instruction=AppealInstruction(remedy="einspruch", evidence_text="x"),
        requirements=[Requirement(text="Belege", kind="document")],
    )
    actions = detect_actions("Was muss ich tun?", analysis, _answer())
    labels = [a.label for a in actions]
    assert "Einspruch entwerfen" in labels and "Unterlagen nachreichen" in labels
    assert "Um Fristverlängerung bitten" not in labels  # never offered against a statutory appeal deadline


def test_appointment_action_uses_concern_id():
    actions = detect_actions("Mein Personalausweis läuft ab", None, _answer())
    assert actions[0].kind == "appointment" and actions[0].params == {"concern": "personalausweis"}


def test_form_action():
    assert [a.kind for a in detect_actions("Kannst du mir das Formular ausfüllen?", None, _answer())] == ["form"]


def test_compose_reply_marks_estimates():
    reply = compose_reply(_answer(deadline=Deadline(date=date(2026, 10, 19), confidence="low"), what_should_i_do=["A", "B"]))
    assert "Frist: 19.10.2026 (geschätzt)" in reply and "• A" in reply
