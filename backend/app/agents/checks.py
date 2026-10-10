"""Rule-based checks used by the auditor and the extractor.

These are plain Python (no models), so they are fast and easy to test.
"""
import re

MONTH = (r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|"
         r"aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)")

DATE_PATTERNS = [
    rf"\d{{1,2}}\s+{MONTH}\.?,?\s+\d{{4}}",                      # 14 March 2026
    rf"{MONTH}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}}",      # March 14, 2026
    r"\d{4}[-/.]\d{1,2}[-/.]\d{1,2}",                             # 2026-03-14
    r"\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}",                           # 03/14/2026
]

# A value is only accepted if the line it came from carries one of the "any" words for that
# field and none of the "not" words (so an invoice date cannot be verified as a due date).
FIELD_RULES = {
    "invoice_number": {"any": ["invoice number", "invoice no", "invoice #", "invoice id", "reference"], "not": []},
    "invoice_date":   {"any": ["invoice date", "bill date", "date of issue", "issued", "dated", "date"],
                       "not": ["due", "pay", "ship", "order", "delivery"]},
    "vendor_name":    {"any": ["vendor", "seller", "supplier", "billed by", "from"], "not": []},
    "due_date":       {"any": ["due", "pay by", "payable by", "payment date"], "not": []},
    "subtotal":       {"any": ["subtotal", "sub total", "sub-total", "before tax"], "not": []},
    "tax":            {"any": ["tax", "vat", "gst"], "not": []},
    "total":          {"any": ["total", "amount due", "amount payable", "balance due"],
                       "not": ["subtotal", "sub total", "sub-total"]},
}


def looks_like_date(value) -> bool:
    v = str(value).strip()
    return any(re.fullmatch(p, v, re.I) for p in DATE_PATTERNS)


def looks_like_money(value) -> bool:
    v = re.sub(r"^(?:usd|eur|gbp|inr|rs\.?)\s*", "", str(value).strip(), flags=re.I)
    v = v.lstrip("$\u20ac\u00a3\u20b9").strip()
    return re.fullmatch(r"\d[\d,]*(?:\.\d{1,2})?", v) is not None


def _label_words(field: str) -> set:
    words = {w for k in FIELD_RULES[field]["any"] for w in re.findall(r"[a-z]+", k)}
    return words | {"name", "company", "number", "no", "id"}


def type_problem(field: str, value):
    """Why a value cannot be right for this field, or None if it looks plausible."""
    v = str(value or "").strip()
    if not v:
        return "empty"
    if field in ("invoice_date", "due_date") and not looks_like_date(v):
        return "not_a_date"
    if field in ("subtotal", "tax", "total") and not looks_like_money(v):
        return "not_an_amount"
    if field == "invoice_number" and not re.search(r"\d", v):
        return "no_digits"
    if field == "vendor_name":
        words = re.findall(r"[a-z]+", v.lower())
        if not words or all(w in _label_words("vendor_name") for w in words):
            return "is_a_label"
    return None


def evidence_for(value, source_text: str) -> list:
    """Lines of the invoice that contain the value. If a value sits alone on its line
    (two-column layout), the label on the line before it is included."""
    lines = [l.strip() for l in source_text.split("\n") if l.strip()]
    v = str(value).strip().lower()
    found = []
    for i, line in enumerate(lines):
        if v and v in line.lower():
            if line.lower() == v and i > 0:
                found.append(f"{lines[i - 1]} {line}")
            else:
                found.append(line)
    return found


def labelled_evidence(field: str, evidence: list) -> list:
    rule = FIELD_RULES.get(field)
    if rule is None:
        return list(evidence)
    kept = []
    for e in evidence:
        low = e.lower()
        if any(k in low for k in rule["any"]) and not any(n in low for n in rule["not"]):
            kept.append(e)
    return kept


def snap_to_line(value: str, source_text: str) -> str:
    """Extend a truncated answer to the end of its line, when it starts right after a
    'Label:' or is the start of a line with no other label after it."""
    if not value:
        return value
    for line in source_text.split("\n"):
        idx = line.find(value)
        if idx < 0:
            continue
        prefix = line[:idx].strip()
        rest_after = line[idx + len(value):]
        if prefix.endswith(":") or (prefix == "" and ":" not in rest_after):
            return line[idx:].strip()
    return value
