import sys, os, types
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))

LABELS = {"invoice_number": "Invoice Number", "invoice_date": "Invoice Date",
          "vendor_name": "Vendor", "due_date": "Due Date", "subtotal": "Subtotal",
          "tax": "Tax", "total": "Total"}

BASE = ["Invoice Number: INV-1", "Invoice Date: March 3, 2026", "Vendor: Acme",
        "Subtotal: 100", "Tax: 8", "Total: 108"]
TEXT_WITH_DUE = "\n".join(BASE[:3] + ["Payment Due Date: April 2, 2026"] + BASE[3:])
TEXT_NO_DUE = "\n".join(BASE)

GOOD = {"invoice_number": "INV-1", "invoice_date": "March 3, 2026", "vendor_name": "Acme",
        "due_date": "April 2, 2026", "subtotal": "100", "tax": "8", "total": "108"}


def install_fakes(monkeypatch, first_pass, candidates):
    """Replace the heavy agents with simple stand-ins so only the graph routing is tested."""
    extraction = types.ModuleType("app.agents.extraction")
    extraction.extract_invoice_fields = lambda text: dict(first_pass)
    extraction.candidate_values = lambda field, text, exclude="": [
        c for c in candidates.get(field, []) if c != exclude]

    def audit_fields(fields, text):
        per = {}
        for f, v in fields.items():
            ok = bool(v) and any(LABELS[f] in line and v in line for line in text.split("\n"))
            per[f] = {"supported": ok, "confidence": 0.99 if ok else 0.0}
        rate = sum(r["supported"] for r in per.values()) / len(per)
        return {"per_field": per, "faithfulness_rate": rate}

    auditor = types.ModuleType("app.agents.auditor")
    auditor.audit_fields = audit_fields

    compliance = types.ModuleType("app.agents.compliance")
    compliance.scan_invoice_compliance = lambda text, fields, seen_invoice_numbers: {
        "pii_entities": [], "flags": [], "risk_level": "low"}

    retrieval = types.ModuleType("app.agents.retrieval")
    retrieval.retrieve = lambda query, doc_id, k=3: []

    session = types.ModuleType("app.db.session")
    session.SessionLocal = lambda: types.SimpleNamespace(close=lambda: None)

    queries = types.ModuleType("app.db.queries")
    queries.previously_seen_invoice_numbers = lambda db, doc_id, fields: set()

    for mod in (extraction, auditor, compliance, retrieval, session, queries):
        monkeypatch.setitem(sys.modules, mod.__name__, mod)


def run(text):
    from app.graph.pipeline import pipeline
    return pipeline.invoke({"doc_id": "d1", "source_text": text})


def test_all_fields_verified_skips_repair(monkeypatch):
    install_fakes(monkeypatch, GOOD, {})
    result = run(TEXT_WITH_DUE)
    assert result["needs_review"] is False
    assert result.get("repair_rounds", 0) == 0


def test_repair_fixes_a_missing_field(monkeypatch):
    first = dict(GOOD, subtotal="")
    install_fakes(monkeypatch, first, {"subtotal": ["100"]})
    result = run(TEXT_WITH_DUE)
    assert result["fields"]["subtotal"] == "100"
    assert result["needs_review"] is False
    assert result["repair_rounds"] == 1


def test_unfixable_field_goes_to_review_and_loop_stops(monkeypatch):
    first = dict(GOOD, due_date="March 3, 2026")      # the invoice date, mistaken for a due date
    install_fakes(monkeypatch, first, {"due_date": ["March 3, 2026", "100"]})
    result = run(TEXT_NO_DUE)                          # this invoice has no due date at all
    assert result["fields"]["due_date"] == "March 3, 2026"
    assert result["audit"]["per_field"]["due_date"]["supported"] is False
    assert result["needs_review"] is True
    assert result["repair_rounds"] == 1