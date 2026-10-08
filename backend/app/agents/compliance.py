from transformers import pipeline

_ner = None
def _get_ner():
    global _ner
    if _ner is None:
        _ner = pipeline("token-classification", model="dslim/bert-base-NER", aggregation_strategy="simple")
    return _ner

def scan_invoice_compliance(text: str, fields: dict, seen_invoice_numbers: set[str],
                             amount_threshold: float = 10000.0) -> dict:
    ner = _get_ner()
    entities = ner(text)
    pii = [e for e in entities if e["entity_group"] in ("PER", "LOC")]

    flags = []
    inv_num = fields.get("invoice_number")
    if inv_num in seen_invoice_numbers:
        flags.append("duplicate_invoice_number")

    try:
        subtotal = float(str(fields.get("subtotal", "0")).replace(",", "").strip("$"))
        tax = float(str(fields.get("tax", "0")).replace(",", "").strip("$"))
        total = float(str(fields.get("total", "0")).replace(",", "").strip("$"))
        if abs((subtotal + tax) - total) > 0.5:
            flags.append("total_does_not_match_subtotal_plus_tax")
        if total > amount_threshold:
            flags.append("amount_over_policy_threshold")
    except (ValueError, TypeError):
        flags.append("amount_fields_unparseable")

    return {
        "pii_entities": [{"text": e["word"], "type": e["entity_group"]} for e in pii],
        "flags": flags,
        "risk_level": "high" if flags else "low",
    }