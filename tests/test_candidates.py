import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))

import app.agents.extraction as ex


def fake_qa(monkeypatch):
    monkeypatch.setattr(ex, "_get_qa", lambda: (None, None))
    # a precise answer from the focused line, a worse one from the whole invoice
    monkeypatch.setattr(ex, "_answer_question",
                        lambda tok, model, question, context: "100" if context == "Subtotal: 100" else "999")


TEXT = "Subtotal: 100\nTotal: 108"


def test_focused_lines_are_tried_first(monkeypatch):
    fake_qa(monkeypatch)
    assert ex.candidate_values("subtotal", TEXT) == ["100", "999"]


def test_failed_answer_is_excluded(monkeypatch):
    fake_qa(monkeypatch)
    assert ex.candidate_values("subtotal", TEXT, exclude="999") == ["100"]


def test_two_column_layout_offers_the_next_line(monkeypatch):
    monkeypatch.setattr(ex, "_get_qa", lambda: (None, None))
    monkeypatch.setattr(ex, "_answer_question", lambda tok, model, question, context: "")
    text = "Invoice Number\nINV-4410\nInvoice Date\nApril 22, 2026"
    assert ex.candidate_values("invoice_number", text) == ["INV-4410"]
