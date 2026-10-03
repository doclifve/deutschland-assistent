from __future__ import annotations

import calendar
import re
from datetime import date, timedelta

from .schemas import AppealInstruction, Deadline, LegalReference, RelativeDeadline, Requirement

LAW_SLUGS = {
    "BGB": "bgb", "GG": "gg", "AO": "ao_1977", "STGB": "stgb", "ZPO": "zpo",
    "VWGO": "vwgo", "VWVFG": "vwvfg", "SGG": "sgg", "ESTG": "estg",
    "SGB I": "sgb_1", "SGB II": "sgb_2", "SGB III": "sgb_3", "SGB IV": "sgb_4",
    "SGB V": "sgb_5", "SGB VI": "sgb_6", "SGB VII": "sgb_7", "SGB VIII": "sgb_8",
    "SGB IX": "sgb_9_2018", "SGB X": "sgb_10", "SGB XI": "sgb_11", "SGB XII": "sgb_12",
}
LEGAL_REF = re.compile(
    r"(?P<section>§{1,2}\s*\d+[a-zA-Z]?(?:\s*(?:Abs\.|Absatz)\s*\d+)?)\s+"
    r"(?P<law>(?:SGB\s*[IVXLC]+|BGB|GG|AO|VwVfG|StGB|ZPO|VwGO|SGG|EStG))\b", re.I
)
DATE_RE = re.compile(r"\b(?P<d>0?[1-9]|[12]\d|3[01])\.(?P<m>0?[1-9]|1[0-2])\.(?P<y>20\d{2})\b")
DEADLINE_HINT = re.compile(
    r"\b(frist|bis zum|spätestens|innerhalb|widerspruch|einspruch|klage|beschwerde|"
    r"einzureichen|vorzulegen|nachreichen|antworten|zahlen|überweisen)\b", re.I
)
LEIKA_RE = re.compile(r"\b99\d{12}\b")
AUTHORITY_RE = re.compile(
    r"\b(Jobcenter|Finanzamt|Familienkasse|Krankenkasse|Pflegekasse|Ausländerbehörde|"
    r"Bundesagentur für Arbeit|Deutsche Rentenversicherung|Sozialamt|Wohngeldstelle|"
    r"Bürgeramt|Bezirksamt|Landratsamt|Stadtverwaltung|Versorgungsamt)\b", re.I
)

# --- Explicit legal references and deadlines ---------------------------------

def normalize_law(law: str) -> str:
    return re.sub(r"\s+", " ", law.upper()).strip()


def law_url(law: str, section: str) -> str:
    slug = LAW_SLUGS.get(normalize_law(law))
    if not slug:
        return "https://www.gesetze-im-internet.de/"
    m = re.search(r"\d+[a-zA-Z]?", section)
    return f"https://www.gesetze-im-internet.de/{slug}/__{m.group(0).lower()}.html" if m else f"https://www.gesetze-im-internet.de/{slug}/"


def extract_legal_references(text: str) -> list[LegalReference]:
    out: list[LegalReference] = []
    seen: set[tuple[str, str]] = set()
    for m in LEGAL_REF.finditer(text):
        section = re.sub(r"\s+", " ", m.group("section")).strip()
        law = normalize_law(m.group("law"))
        key = (section.lower(), law)
        if key in seen:
            continue
        seen.add(key)
        out.append(LegalReference(raw=m.group(0), section=section, law=law, source_url=law_url(law, section)))
    return out


def _parse_date(value: str) -> date | None:
    m = DATE_RE.search(value or "")
    if not m:
        return None
    try:
        return date(int(m.group("y")), int(m.group("m")), int(m.group("d")))
    except ValueError:
        return None


def extract_deadlines(text: str, document_date: date | None = None) -> list[Deadline]:
    """Explicit dates near deadline words. The letter's own date is never a deadline."""
    out: list[Deadline] = []
    seen = set() if document_date is None else {document_date}
    for m in DATE_RE.finditer(text):
        context = text[max(0, m.start() - 140) : min(len(text), m.end() + 140)]
        if not DEADLINE_HINT.search(context):
            continue
        parsed = _parse_date(m.group(0))
        if not parsed or parsed in seen:
            continue
        seen.add(parsed)
        out.append(Deadline(date=parsed, label="Im Dokument erkannte Frist", confidence="high", evidence_text=" ".join(context.split())[:300]))
    return sorted(out, key=lambda x: x.date)

# --- Relative deadlines (merged from hardening PR) ----------------------------
_DATE = r"(?P<d>0?[1-9]|[12]\d|3[01])\.(?P<m>0?[1-9]|1[0-2])\.(?P<y>20\d{2})"
DOC_DATE_RE = re.compile(rf"(?:\bDatum\s*:?\s*|\bvom\s+|,\s*(?:den\s+)?){_DATE}\b", re.I)
DOC_DATE_WINDOW = 2000
NUMBER_WORDS = {"ein":1,"eine":1,"eines":1,"einem":1,"einer":1,"zwei":2,"drei":3,"vier":4,"fünf":5,"sechs":6,"sieben":7,"acht":8,"neun":9,"zehn":10,"elf":11,"zwölf":12}
RELATIVE_RE = re.compile(
    r"\b(?:innerhalb|binnen)\s+(?:von\s+)?"
    r"(?P<n>\d{1,3}|" + "|".join(sorted(NUMBER_WORDS, key=len, reverse=True)) + r")\s+"
    r"(?P<unit>Monat(?:s|e|en)?|Woche(?:n)?|Tag(?:e|en)?)\s+"
    r"(?:nach|ab|seit)\s+(?:[\wäöüÄÖÜß]+\s+){0,3}?"
    r"(?P<trigger>Bekanntgabe|Zustellung|Zugang|Erhalt|Eingang)", re.I
)
POSTAL_TRIGGERS = {"bekanntgabe", "zugang", "erhalt", "eingang"}
POSTMODG_CUTOFF = date(2025, 1, 1)


def _match_date(m: re.Match) -> date | None:
    try:
        return date(int(m.group("y")), int(m.group("m")), int(m.group("d")))
    except ValueError:
        return None


def extract_document_date(text: str) -> date | None:
    m = DOC_DATE_RE.search(text[:DOC_DATE_WINDOW])
    return _match_date(m) if m else None


def add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    year, month = d.year + y, m + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def next_weekday(d: date) -> date:
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def period_end(trigger_day: date, value: int, unit: str) -> date:
    if unit == "months":
        end = add_months(trigger_day, value)
    elif unit == "weeks":
        end = trigger_day + timedelta(weeks=value)
    else:
        end = trigger_day + timedelta(days=value)
    return next_weekday(end)


def extract_relative_deadlines(text: str, document_date: date | None = None) -> list[RelativeDeadline]:
    out: list[RelativeDeadline] = []
    seen: set[tuple[int, str, str]] = set()
    for m in RELATIVE_RE.finditer(text):
        n = m.group("n")
        value = int(n) if n.isdigit() else NUMBER_WORDS[n.lower()]
        u = m.group("unit").lower()
        unit = "months" if u.startswith("monat") else "weeks" if u.startswith("woche") else "days"
        trigger = m.group("trigger").capitalize()
        key = (value, unit, trigger)
        if key in seen:
            continue
        seen.add(key)
        rd = RelativeDeadline(raw=" ".join(m.group(0).split()), period_value=value, period_unit=unit, trigger=trigger, document_date=document_date)
        if document_date and trigger.lower() in POSTAL_TRIGGERS:
            days = 4 if document_date >= POSTMODG_CUTOFF else 3
            rd.assumed_trigger_date = document_date + timedelta(days=days)
            rd.estimated_end = period_end(rd.assumed_trigger_date, value, unit)
            rd.basis = [
                f"Annahme: Versand per Post am Datum des Schreibens; Bekanntgabe gilt am {'vierten' if days == 4 else 'dritten'} Tag danach (§ 37 Abs. 2 SGB X, § 41 Abs. 2 VwVfG, § 122 Abs. 2 AO).",
                "Fristberechnung nach §§ 187 Abs. 1, 188 BGB; Fristende am Wochenende verschiebt sich auf Montag.",
                "Feiertage sind nicht berücksichtigt. Das tatsächliche Fristende kann später liegen, nicht früher.",
            ]
        elif trigger.lower() == "zustellung":
            rd.basis = ["Bei förmlicher Zustellung zählt das Zustelldatum (z. B. auf dem gelben Umschlag); keine Schätzung möglich."]
        else:
            rd.basis = ["Kein Datum des Schreibens erkannt; Fristende kann nicht geschätzt werden."]
        out.append(rd)
    return out

# --- Requirements / demands ---------------------------------------------------
REQUEST_PATTERNS = [
    re.compile(r"(?:bitte\s+)?reichen\s+Sie\s+(.{4,220}?)\s+(?:ein|nach)(?:[\.,;]|$)", re.I),
    re.compile(r"(?:bitte\s+)?legen\s+Sie\s+(.{4,220}?)\s+vor(?:[\.,;]|$)", re.I),
    re.compile(r"(?:bitte\s+)?übermitteln\s+Sie\s+(.{4,220}?)(?:[\.,;]|$)", re.I),
    re.compile(r"Sie\s+werden\s+(?:hiermit\s+)?aufgefordert,?\s+(.{4,260}?)(?:[\.;]|$)", re.I),
    re.compile(r"wir\s+benötigen\s+(?:noch\s+)?(.{4,220}?)(?:[\.;]|$)", re.I),
    re.compile(r"wir\s+bitten\s+Sie,?\s+(.{4,260}?)(?:[\.;]|$)", re.I),
]
PAYMENT_PATTERN = re.compile(r"(?:zahlen|überweisen)\s+Sie\s+(.{3,180}?)(?:\s+bis\s+zum\s+(\d{1,2}\.\d{1,2}\.20\d{2}))?(?:[\.;]|$)", re.I)
BULLET_RE = re.compile(r"^(?:[-•*▪‣]|\d+[\.)])\s*(.{3,220})$")
REQUIREMENT_HEADING = re.compile(r"(?:folgende|nachfolgende)\s+(?:unterlagen|nachweise|angaben)|(?:wir\s+benötigen|bitte\s+reichen\s+Sie\s+folgende)", re.I)


def _requirement_kind(value: str) -> str:
    v = value.lower()
    if any(x in v for x in ["kontoausz", "nachweis", "bescheinigung", "vertrag", "abrechnung", "kopie", "urkunde", "formular"]):
        return "document"
    if any(x in v for x in ["zahlen", "überweisen", "betrag", "euro", "€"]):
        return "payment"
    if any(x in v for x in ["mitteilen", "angeben", "auskunft", "information"]):
        return "information"
    if any(x in v for x in ["erscheinen", "melden", "termin", "unterschreiben", "beantragen"]):
        return "action"
    return "unknown"


def extract_requirements(text: str) -> list[Requirement]:
    clean = re.sub(r"\r\n?", "\n", text)
    found: list[Requirement] = []
    seen: set[str] = set()

    def add(value: str, evidence: str, kind: str | None = None, due: date | None = None, confidence: str = "high") -> None:
        value = re.sub(r"\s+", " ", value).strip(" .,:;-")
        if len(value) < 3:
            return
        key = value.lower()
        if key in seen:
            return
        seen.add(key)
        found.append(Requirement(text=value, kind=kind or _requirement_kind(value), due_date=due, confidence=confidence, evidence_text=" ".join(evidence.split())[:320]))

    flat = re.sub(r"\s+", " ", clean)
    for pattern in REQUEST_PATTERNS:
        for m in pattern.finditer(flat):
            add(m.group(1), m.group(0))
    for m in PAYMENT_PATTERN.finditer(flat):
        add(m.group(1), m.group(0), kind="payment", due=_parse_date(m.group(2) or ""))

    lines = [line.strip() for line in clean.splitlines()]
    heading_window = 0
    for line in lines:
        if not line:
            if heading_window > 0:
                heading_window -= 1
            continue
        if REQUIREMENT_HEADING.search(line):
            heading_window = 8
            continue
        bullet = BULLET_RE.match(line)
        if bullet and heading_window > 0:
            add(bullet.group(1), line, confidence="high")
            heading_window -= 1
        elif heading_window > 0:
            heading_window -= 1
    return found[:20]


def extract_requested_items(text: str) -> list[str]:
    return [r.text for r in extract_requirements(text) if r.kind in {"document", "information", "unknown"}][:12]

# --- Rechtsbehelfsbelehrung ---------------------------------------------------
APPEAL_HEADING = re.compile(r"rechtsbehelfsbelehrung|rechtsmittelbelehrung", re.I)
APPEAL_REMEDY = re.compile(r"\b(widerspruch|einspruch|klage|beschwerde)\b", re.I)
RELATIVE_APPEAL_DEADLINE = re.compile(r"\b(innerhalb\s+(?:eines|einer|von\s+\d+)\s+(?:monats?|wochen?|tagen?)(?:\s+nach\s+[^\.;\n]{2,120})?)", re.I)
RECIPIENT_RE = re.compile(r"(?:bei|an)\s+(?:dem|der|das)?\s*([^\n\.;]{5,180}?)(?=\s+(?:schriftlich|elektronisch|zur\s+niederschrift|einzulegen|zu\s+erheben)|[\.;\n])", re.I)


def extract_appeal_instruction(text: str) -> AppealInstruction | None:
    heading = APPEAL_HEADING.search(text)
    if heading:
        chunk = text[heading.start() : heading.start() + 3500]
        heading_present = True
    else:
        candidates = [m for m in APPEAL_REMEDY.finditer(text)]
        candidates = [m for m in candidates if re.search(r"innerhalb|einlegen|erheben|bekanntgabe|zustellung", text[max(0, m.start() - 500) : m.end() + 1200], re.I)]
        if not candidates:
            return None
        start = candidates[0].start()
        chunk = text[max(0, start - 500) : start + 2200]
        heading_present = False

    remedy_match = APPEAL_REMEDY.search(chunk)
    remedy = remedy_match.group(1).lower() if remedy_match else "unknown"
    relative = RELATIVE_APPEAL_DEADLINE.search(chunk)
    explicit = None
    for dm in DATE_RE.finditer(chunk):
        context = chunk[max(0, dm.start() - 100) : dm.end() + 100]
        if DEADLINE_HINT.search(context):
            explicit = _parse_date(dm.group(0))
            if explicit:
                break
    recipient_match = RECIPIENT_RE.search(chunk)
    recipient = re.sub(r"\s+", " ", recipient_match.group(1)).strip(" ,") if recipient_match else None
    methods = []
    for label, pattern in [("schriftlich", r"\bschriftlich\b"), ("elektronisch", r"\belektronisch\b"), ("zur Niederschrift", r"\bzur\s+niederschrift\b")]:
        if re.search(pattern, chunk, re.I):
            methods.append(label)
    return AppealInstruction(
        remedy=remedy if remedy in {"widerspruch", "einspruch", "klage", "beschwerde"} else "unknown",
        deadline_expression=re.sub(r"\s+", " ", relative.group(1)).strip() if relative else None,
        explicit_deadline=explicit,
        recipient=recipient,
        methods=methods,
        evidence_text=" ".join(chunk.split())[:1400],
        confidence="high" if heading_present and remedy != "unknown" else "medium",
    )

# --- Shared document features -------------------------------------------------
def extract_leika_ids(text: str) -> list[str]:
    return list(dict.fromkeys(LEIKA_RE.findall(text)))


def extract_authority_hint(text: str) -> str | None:
    m = AUTHORITY_RE.search(text[:5000])
    return m.group(0) if m else None


def classify_document(text: str) -> str:
    t = text.lower()
    if any(x in t for x in ["bescheid", "rechtsbehelfsbelehrung", "widerspruchsbelehrung"]):
        return "authority_decision"
    if any(x in t for x in ["aufforderung zur mitwirkung", "mitwirkungspflicht"]):
        return "authority_request"
    if "rechnung" in t:
        return "invoice"
    if any(x in t for x in ["vertrag", "kündigung"]):
        return "contract_or_notice"
    return "unknown"
