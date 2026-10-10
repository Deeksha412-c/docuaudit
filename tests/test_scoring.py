import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "evaluation"))
from metrics import score_results

GOLD = [{"doc_id": "a", "gold_fields": {"invoice_number": "INV-1", "due_date": ""}}]


def prediction(fields, supported, flags=None):
    return {"fields": fields,
            "audit": {"per_field": {f: {"supported": s} for f, s in supported.items()}},
            "compliance": {"flags": flags or []}}


def score(pred):
    return score_results(GOLD, {"a": pred})


def test_perfect_run():
    r = score(prediction({"invoice_number": "INV-1", "due_date": ""},
                         {"invoice_number": True, "due_date": False}))
    assert r["summary"] == {"field_f1": 1.0, "faithfulness": 1.0, "verified_precision": 1.0,
                            "flag_accuracy": 1.0, "absent_fields_flagged": 1.0}
    assert r["mistakes"] == []


def test_wrong_value_caught_by_the_auditor():
    r = score(prediction({"invoice_number": "INV-9", "due_date": ""},
                         {"invoice_number": False, "due_date": False}))
    assert r["summary"]["field_f1"] == 0.0
    assert r["summary"]["verified_precision"] == 1.0      # nothing wrong was verified
    assert r["mistakes"][0]["verified"] is False


def test_wrong_value_that_slipped_through():
    r = score(prediction({"invoice_number": "INV-9", "due_date": ""},
                         {"invoice_number": True, "due_date": False}))
    assert r["summary"]["verified_precision"] == 0.0
    assert r["mistakes"][0]["verified"] is True


def test_invented_value_for_a_field_that_is_not_on_the_invoice():
    r = score(prediction({"invoice_number": "INV-1", "due_date": "March 3, 2026"},
                         {"invoice_number": True, "due_date": True}))
    assert r["summary"]["absent_fields_flagged"] == 0.0
    assert r["summary"]["verified_precision"] == 0.5      # one of two verified values was right


def test_unexpected_compliance_flag_is_a_mistake():
    r = score(prediction({"invoice_number": "INV-1", "due_date": ""},
                         {"invoice_number": True, "due_date": False},
                         flags=["duplicate_invoice_number"]))
    assert r["summary"]["flag_accuracy"] == 0.0
    assert r["mistakes"][0]["field"] == "compliance flags"