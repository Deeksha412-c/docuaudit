from transformers import pipeline

_nli = None
def _get_nli():
    global _nli
    if _nli is None:
        _nli = pipeline("text-classification", model="cross-encoder/nli-deberta-v3-base")
    return _nli

FIELD_TEMPLATES = {
    "invoice_number": "The invoice number is {v}.",
    "invoice_date":   "The invoice date is {v}.",
    "vendor_name":    "The vendor is {v}.",
    "due_date":       "The payment due date is {v}.",
    "subtotal":       "The subtotal is {v}.",
    "tax":            "The tax is {v}.",
    "total":          "The total amount due is {v}.",
}

def _evidence_lines(value: str, source_text: str) -> str:
    v = str(value).strip().lower()
    lines = [l.strip() for l in source_text.split("\n") if v and v in l.lower()]
    return " ".join(lines)

def audit_fields(fields: dict, source_text: str, threshold: float = 0.6) -> dict:
    nli = _get_nli()
    results = {}
    for field, value in fields.items():
        if not value:
            results[field] = {"supported": False, "confidence": 0.0, "reason": "empty"}
            continue
        evidence = _evidence_lines(value, source_text)
        if not evidence:
            results[field] = {"supported": False, "confidence": 0.0, "reason": "not_in_source"}
            continue
        hypothesis = FIELD_TEMPLATES.get(field, "{v}").format(v=value)
        r = nli(evidence, text_pair=hypothesis)[0]
        supported = r["label"].lower() == "entailment" and r["score"] >= threshold
        results[field] = {
            "supported": supported,
            "confidence": round(r["score"], 3),
            "evidence": evidence,
        }
    rate = sum(1 for r in results.values() if r["supported"]) / max(len(results), 1)
    return {"per_field": results, "faithfulness_rate": rate}