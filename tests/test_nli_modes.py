import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))

import app.agents.auditor as au

TEXT = "Invoice Number: INV-1\nTotal Amount Due: $100.00"


def fake_nli(label, score=0.9):
    return lambda premise, text_pair=None: [{"label": label, "score": score}]


def audit(monkeypatch, mode, label):
    monkeypatch.setenv("DOCUAUDIT_NLI_MODE", mode)
    monkeypatch.setattr(au, "_get_nli", lambda: fake_nli(label))
    return au.audit_fields({"total": "$100.00"}, TEXT)["per_field"]["total"]


def test_strict_needs_clear_support(monkeypatch):
    assert audit(monkeypatch, "strict", "entailment")["supported"] is True
    assert audit(monkeypatch, "strict", "neutral")["supported"] is False
    assert audit(monkeypatch, "strict", "contradiction")["supported"] is False


def test_veto_rejects_only_a_clear_contradiction(monkeypatch):
    assert audit(monkeypatch, "veto", "entailment")["supported"] is True
    assert audit(monkeypatch, "veto", "neutral")["supported"] is True
    assert audit(monkeypatch, "veto", "contradiction")["supported"] is False


def test_off_skips_the_language_model(monkeypatch):
    monkeypatch.setenv("DOCUAUDIT_NLI_MODE", "off")

    def must_not_be_called():
        raise AssertionError("the language model should not be loaded in off mode")

    monkeypatch.setattr(au, "_get_nli", must_not_be_called)
    result = au.audit_fields({"total": "$100.00"}, TEXT)["per_field"]["total"]
    assert result["supported"] is True and result["mode"] == "rules_only"


def test_the_rules_still_apply_when_the_model_is_off(monkeypatch):
    monkeypatch.setenv("DOCUAUDIT_NLI_MODE", "off")
    monkeypatch.setattr(au, "_get_nli", lambda: fake_nli("entailment"))
    result = au.audit_fields({"total": "Total Amount Due"}, TEXT)["per_field"]["total"]
    assert result["supported"] is False and result["reason"] == "not_an_amount"


def test_veto_is_the_default_mode(monkeypatch):
    monkeypatch.delenv("DOCUAUDIT_NLI_MODE", raising=False)
    monkeypatch.setattr(au, "_get_nli", lambda: fake_nli("neutral"))
    assert au.audit_fields({"total": "$100.00"}, TEXT)["per_field"]["total"]["supported"] is True


def test_the_models_label_is_recorded_next_to_its_score(monkeypatch):
    result = audit(monkeypatch, "veto", "neutral")
    assert result["nli_label"] == "neutral"
