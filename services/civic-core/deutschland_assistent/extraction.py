from __future__ import annotations
import calendar
import re
from datetime import date, timedelta
from .schemas import Deadline, LegalReference, RelativeDeadline

LAW_SLUGS={"BGB":"bgb","GG":"gg","AO":"ao_1977","STGB":"stgb","ZPO":"zpo","VWGO":"vwgo","VWVFG":"vwvfg","SGG":"sgg","ESTG":"estg","SGB I":"sgb_1","SGB II":"sgb_2","SGB III":"sgb_3","SGB IV":"sgb_4","SGB V":"sgb_5","SGB VI":"sgb_6","SGB VII":"sgb_7","SGB VIII":"sgb_8","SGB IX":"sgb_9_2018","SGB X":"sgb_10","SGB XI":"sgb_11","SGB XII":"sgb_12"}
LEGAL_REF=re.compile(r"(?P<section>§{1,2}\s*\d+[a-zA-Z]?(?:\s*(?:Abs\.|Absatz)\s*\d+)?)\s+(?P<law>(?:SGB\s*[IVXLC]+|BGB|GG|AO|VwVfG|StGB|ZPO|VwGO|SGG|EStG))\b",re.I)
DATE_RE=re.compile(r"\b(?P<d>0?[1-9]|[12]\d|3[01])\.(?P<m>0?[1-9]|1[0-2])\.(?P<y>20\d{2})\b")
DEADLINE_HINT=re.compile(r"\b(frist|bis zum|spätestens|innerhalb|widerspruch|einzureichen|vorzulegen|nachreichen|antworten)\b",re.I)
LEIKA_RE=re.compile(r"\b99\d{12}\b")
AUTHORITY_RE=re.compile(r"\b(Jobcenter|Finanzamt|Familienkasse|Krankenkasse|Pflegekasse|Ausländerbehörde|Bundesagentur für Arbeit|Deutsche Rentenversicherung|Sozialamt|Wohngeldstelle|Bürgeramt|Bezirksamt|Landratsamt|Stadtverwaltung)\b",re.I)
REQUEST_LINE=re.compile(r"^(?:[-•*]\s*)?(?:bitte\s+)?(?:reichen|senden|legen|übermitteln|fügen)\s+Sie\s+(.{4,180})$",re.I)

def normalize_law(law:str)->str:
    return re.sub(r"\s+"," ",law.upper()).strip()

def law_url(law:str,section:str)->str:
    slug=LAW_SLUGS.get(normalize_law(law))
    if not slug:return "https://www.gesetze-im-internet.de/"
    m=re.search(r"\d+[a-zA-Z]?",section)
    return f"https://www.gesetze-im-internet.de/{slug}/__{m.group(0).lower()}.html" if m else f"https://www.gesetze-im-internet.de/{slug}/"

def extract_legal_references(text:str)->list[LegalReference]:
    out=[];seen=set()
    for m in LEGAL_REF.finditer(text):
        section=re.sub(r"\s+"," ",m.group("section")).strip();law=normalize_law(m.group("law"));key=(section.lower(),law)
        if key in seen:continue
        seen.add(key);out.append(LegalReference(raw=m.group(0),section=section,law=law,source_url=law_url(law,section)))
    return out

def extract_deadlines(text:str,document_date:date|None=None)->list[Deadline]:
    """Explicit dates near deadline words. The letter's own date is never a deadline."""
    out=[];seen=set() if document_date is None else {document_date}
    for m in DATE_RE.finditer(text):
        context=text[max(0,m.start()-120):min(len(text),m.end()+120)]
        if not DEADLINE_HINT.search(context):continue
        try:parsed=date(int(m.group("y")),int(m.group("m")),int(m.group("d")))
        except ValueError:continue
        if parsed in seen:continue
        seen.add(parsed);out.append(Deadline(date=parsed,label="Im Dokument erkannte Frist",confidence="high",evidence_text=" ".join(context.split())[:260]))
    return sorted(out,key=lambda x:x.date)

# --- Relative Fristen -------------------------------------------------------
# Computed dates are deliberately conservative: when in doubt we produce an
# *earlier* date than the true legal deadline, never a later one.

_DATE=r"(?P<d>0?[1-9]|[12]\d|3[01])\.(?P<m>0?[1-9]|1[0-2])\.(?P<y>20\d{2})"
# "Datum: 12.09.2026", "vom 12.09.2026", "Hamburg, den 12.09.2026", "Hamburg, 12.09.2026"
DOC_DATE_RE=re.compile(rf"(?:\bDatum\s*:?\s*|\bvom\s+|,\s*(?:den\s+)?){_DATE}\b",re.I)
DOC_DATE_WINDOW=2000
NUMBER_WORDS={"ein":1,"eine":1,"eines":1,"einem":1,"einer":1,"zwei":2,"drei":3,"vier":4,"fünf":5,"sechs":6,"sieben":7,"acht":8,"neun":9,"zehn":10,"elf":11,"zwölf":12}
RELATIVE_RE=re.compile(
    r"\b(?:innerhalb|binnen)\s+(?:von\s+)?"
    r"(?P<n>\d{1,3}|"+"|".join(sorted(NUMBER_WORDS,key=len,reverse=True))+r")\s+"
    r"(?P<unit>Monat(?:s|e|en)?|Woche(?:n)?|Tag(?:e|en)?)\s+"
    r"(?:nach|ab|seit)\s+(?:[\wäöüÄÖÜß]+\s+){0,3}?"
    r"(?P<trigger>Bekanntgabe|Zustellung|Zugang|Erhalt|Eingang)",re.I)
POSTAL_TRIGGERS={"bekanntgabe","zugang","erhalt","eingang"}
POSTMODG_CUTOFF=date(2025,1,1)

def _match_date(m:re.Match)->date|None:
    try:return date(int(m.group("y")),int(m.group("m")),int(m.group("d")))
    except ValueError:return None

def extract_document_date(text:str)->date|None:
    """Date the letter was issued, only if it is marked as such near the top."""
    m=DOC_DATE_RE.search(text[:DOC_DATE_WINDOW]);return _match_date(m) if m else None

def add_months(d:date,months:int)->date:
    """§ 188 Abs. 2, 3 BGB: same day number, or the last day of a shorter month."""
    y,m=divmod(d.month-1+months,12);year,month=d.year+y,m+1
    return date(year,month,min(d.day,calendar.monthrange(year,month)[1]))

def next_weekday(d:date)->date:
    """§ 193 BGB / § 31 Abs. 3 VwVfG / § 26 Abs. 3 SGB X / § 108 Abs. 3 AO (weekends only)."""
    while d.weekday()>=5:d+=timedelta(days=1)
    return d

def period_end(trigger_day:date,value:int,unit:str)->date:
    """§ 187 Abs. 1, § 188 BGB: the trigger day is not counted."""
    if unit=="months":end=add_months(trigger_day,value)
    elif unit=="weeks":end=trigger_day+timedelta(weeks=value)
    else:end=trigger_day+timedelta(days=value)
    return next_weekday(end)

def extract_relative_deadlines(text:str,document_date:date|None=None)->list[RelativeDeadline]:
    out=[];seen=set()
    for m in RELATIVE_RE.finditer(text):
        n=m.group("n");value=int(n) if n.isdigit() else NUMBER_WORDS[n.lower()]
        u=m.group("unit").lower();unit="months" if u.startswith("monat") else "weeks" if u.startswith("woche") else "days"
        trigger=m.group("trigger").capitalize();key=(value,unit,trigger)
        if key in seen:continue
        seen.add(key)
        rd=RelativeDeadline(raw=" ".join(m.group(0).split()),period_value=value,period_unit=unit,trigger=trigger,document_date=document_date)
        if document_date and trigger.lower() in POSTAL_TRIGGERS:
            days=4 if document_date>=POSTMODG_CUTOFF else 3
            rd.assumed_trigger_date=document_date+timedelta(days=days)
            rd.estimated_end=period_end(rd.assumed_trigger_date,value,unit)
            rd.basis=[f"Annahme: Versand per Post am Datum des Schreibens; Bekanntgabe gilt am {'vierten' if days==4 else 'dritten'} Tag danach (§ 37 Abs. 2 SGB X, § 41 Abs. 2 VwVfG, § 122 Abs. 2 AO).",
                      "Fristberechnung nach §§ 187 Abs. 1, 188 BGB; Fristende am Wochenende verschiebt sich auf Montag.",
                      "Feiertage sind nicht berücksichtigt. Das tatsächliche Fristende kann später liegen, nicht früher."]
        elif trigger.lower()=="zustellung":
            rd.basis=["Bei förmlicher Zustellung zählt das Zustelldatum (z. B. auf dem gelben Umschlag); keine Schätzung möglich."]
        else:
            rd.basis=["Kein Datum des Schreibens erkannt; Fristende kann nicht geschätzt werden."]
        out.append(rd)
    return out

def extract_leika_ids(text:str)->list[str]:
    return list(dict.fromkeys(LEIKA_RE.findall(text)))

def extract_authority_hint(text:str)->str|None:
    m=AUTHORITY_RE.search(text[:5000]);return m.group(0) if m else None

def extract_requested_items(text:str)->list[str]:
    items=[]
    for line in [re.sub(r"\s+"," ",x).strip() for x in text.splitlines() if x.strip()]:
        m=REQUEST_LINE.match(line)
        if m:
            item=m.group(1).strip(" .:")
            if item and item not in items:items.append(item)
    return items[:12]

def classify_document(text:str)->str:
    t=text.lower()
    if any(x in t for x in ["bescheid","rechtsbehelfsbelehrung","widerspruchsbelehrung"]):return "authority_decision"
    if any(x in t for x in ["aufforderung zur mitwirkung","mitwirkungspflicht"]):return "authority_request"
    if "rechnung" in t:return "invoice"
    if any(x in t for x in ["vertrag","kündigung"]):return "contract_or_notice"
    return "unknown"
