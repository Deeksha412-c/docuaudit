import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))
from app.agents.compliance import scan_invoice_compliance

def test_flags_mismatched_total():
    fields = {"invoice_number": "INV-1", "subtotal": "100.00", "tax": "8.00", "total": "999.00"}
    result = scan_invoice_compliance("Invoice text here", fields, seen_invoice_numbers=set())
    assert "total_does_not_match_subtotal_plus_tax" in result["flags"]

def test_flags_duplicate_invoice_number():
    fields = {"invoice_number": "INV-1", "subtotal": "100.00", "tax": "8.00", "total": "108.00"}
    result = scan_invoice_compliance("Invoice text", fields, seen_invoice_numbers={"INV-1"})
    assert "duplicate_invoice_number" in result["flags"]