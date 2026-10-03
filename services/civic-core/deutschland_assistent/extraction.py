from __future__ import annotations
import re
from datetime import date
from .schemas import Deadline, LegalReference

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

def extract_deadlines(text:str)->list[Deadline]:
    out=[];seen=set()
    for m in DATE_RE.finditer(text):
        context=text[max(0,m.start()-120):min(len(text),m.end()+120)]
        if not DEADLINE_HINT.search(context):continue
        try:parsed=date(int(m.group("y")),int(m.group("m")),int(m.group("d")))
        except ValueError:continue
        if parsed in seen:continue
        seen.add(parsed);out.append(Deadline(date=parsed,label="Im Dokument erkannte Frist",confidence="high",evidence_text=" ".join(context.split())[:260]))
    return sorted(out,key=lambda x:x.date)

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
