def _norm(s) -> str:
    s = str(s).lower().replace("$", "").replace(",", "").strip()
    return s.rstrip(".")


def compute_f1(pred: str, gold: str) -> float:
    pred_tokens, gold_tokens = set(_norm(pred).split()), set(_norm(gold).split())
    if not pred_tokens or not gold_tokens:
        return 0.0
    overlap = pred_tokens & gold_tokens
    precision = len(overlap) / len(pred_tokens)
    recall = len(overlap) / len(gold_tokens)
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)


def score_results(golden: list, predictions: dict) -> dict:
    """Score pipeline output against hand-labelled invoices.

    golden:      [{"doc_id", "gold_fields": {...}, "expected_flags": [...] (optional)}]
    predictions: {doc_id: pipeline result containing "fields", "audit" and "compliance"}
    A gold value of "" means the invoice does not contain that field.
    """
    f1_scores, per_field = [], {}
    present = verified_present = 0
    verified_total = verified_correct = 0
    absent = absent_flagged = 0
    flag_matches = 0
    mistakes = []

    for item in golden:
        doc_id = item["doc_id"]
        pred = predictions[doc_id]
        audit = pred["audit"]["per_field"]

        for field, gold in item["gold_fields"].items():
            value = pred["fields"].get(field, "")
            verified = bool(audit.get(field, {}).get("supported", False))

            if gold == "":                                   # field is not on the invoice
                absent += 1
                if verified:
                    verified_total += 1
                    mistakes.append(dict(doc_id=doc_id, field=field, gold="(not on invoice)",
                                         predicted=value, verified=True))
                else:
                    absent_flagged += 1
                continue

            f1 = compute_f1(value, gold)
            f1_scores.append(f1)
            per_field.setdefault(field, []).append(f1)
            present += 1
            correct = f1 >= 0.999
            if verified:
                verified_present += 1
                verified_total += 1
                verified_correct += int(correct)
            if not correct:
                mistakes.append(dict(doc_id=doc_id, field=field, gold=gold,
                                     predicted=value, verified=verified))

        expected = sorted(item.get("expected_flags", []))
        got = sorted(pred["compliance"]["flags"])
        if got == expected:
            flag_matches += 1
        else:
            mistakes.append(dict(doc_id=doc_id, field="compliance flags", gold=expected,
                                 predicted=got, verified=None))

    summary = {
        "field_f1": round(sum(f1_scores) / len(f1_scores), 3) if f1_scores else 0.0,
        "faithfulness": round(verified_present / present, 3) if present else 0.0,
        "verified_precision": round(verified_correct / verified_total, 3) if verified_total else 1.0,
        "flag_accuracy": round(flag_matches / len(golden), 3) if golden else 0.0,
    }
    if absent:
        summary["absent_fields_flagged"] = round(absent_flagged / absent, 3)

    return {
        "summary": summary,
        "per_field": {f: round(sum(v) / len(v), 3) for f, v in per_field.items()},
        "mistakes": mistakes,
    }