import os
from transformers import pipeline
from app.agents.checks import type_problem, evidence_for, labelled_evidence

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


def _rejected(reason: str) -> dict:
    return {"supported": False, "confidence": 0.0, "reason": reason}


def audit_fields(fields: dict, source_text: str, threshold: float = 0.6) -> dict:
    """A field is verified only if it passes these checks:
    1. its type fits the field (a date for a date field, an amount for an amount field, ...)
    2. the line it came from carries the right label (an invoice date cannot be a due date)
    3. the language model, depending on DOCUAUDIT_NLI_MODE:
         veto (default)  the value is rejected only if the labelled line clearly contradicts it
         strict          the labelled line must clearly support the claim
         off             no language-model check; the rules alone decide
    """
    mode = os.environ.get("DOCUAUDIT_NLI_MODE", "veto").lower()
    results = {}
    for field, value in fields.items():
        problem = type_problem(field, value)
        if problem:
            results[field] = _rejected(problem)
            continue

        evidence = evidence_for(value, source_text)
        if not evidence:
            results[field] = _rejected("not_in_source")
            continue

        labelled = labelled_evidence(field, evidence)
        if not labelled:
            results[field] = _rejected("label_mismatch")
            continue

        premise = " ".join(labelled)
        if mode == "off":
            results[field] = {"supported": True, "confidence": None, "evidence": premise, "mode": "rules_only"}
            continue

        hypothesis = FIELD_TEMPLATES.get(field, "{v}").format(v=value)
        r = _get_nli()(premise, text_pair=hypothesis)[0]
        label, score = r["label"].lower(), r["score"]
        if mode == "veto":
            supported = not (label == "contradiction" and score >= threshold)
        else:
            supported = label == "entailment" and score >= threshold
        results[field] = {"supported": supported, "confidence": round(score, 3),
                         "nli_label": label, "evidence": premise}

    rate = sum(1 for r in results.values() if r["supported"]) / max(len(results), 1)
    return {"per_field": results, "faithfulness_rate": rate}
