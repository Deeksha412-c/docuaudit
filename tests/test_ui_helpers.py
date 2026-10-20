import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "frontend"))

import pymupdf
from ui_helpers import field_rows, locate, render_pages, why_not, flag_label, status_pill


def make_pdf(lines):
    doc = pymupdf.open()
    page = doc.new_page()
    y = 72
    for line in lines:
        page.insert_text((72, y), line, fontsize=11)
        y += 18
    data = doc.tobytes()
    doc.close()
    return data


def result_with(per_field, fields):
    return {"status": "needs_review", "extraction": fields, "audit": {"per_field": per_field}}


def test_rows_follow_a_fixed_order_and_mark_unverified_fields():
    result = result_with(
        {"invoice_number": {"supported": True, "evidence": "Invoice Number: INV-1"},
         "due_date": {"supported": False, "reason": "label_mismatch"}},
        {"invoice_number": "INV-1", "due_date": "March 3, 2026"})
    rows = {r["key"]: r for r in field_rows(result)}
    assert [r["key"] for r in field_rows(result)][:2] == ["invoice_number", "invoice_date"]
    assert rows["invoice_number"]["verified"] is True and rows["invoice_number"]["note"] is None
    assert rows["due_date"]["verified"] is False and rows["due_date"]["note"] == "Not next to the right label"


def test_reasons_are_written_in_plain_language():
    assert why_not({"reason": "not_a_date"}) == "Not a date"
    assert why_not({"nli_label": "contradiction"}) == "The invoice line contradicts this value"
    assert why_not({"nli_label": "neutral"}) == "The invoice line does not clearly support this value"


def test_labels_and_statuses():
    assert flag_label("duplicate_invoice_number") == "Possible duplicate"
    assert flag_label("something_new") == "Something new"
    assert status_pill("needs_review") == ("Needs review", "warn")


def test_a_repeated_value_is_placed_on_its_evidence_line():
    pdf = make_pdf(["Packaging fee  $80.00", "Setup fee  $80.00", "Tax: $80.00"])
    rows = [{"key": "tax", "value": "$80.00", "evidence": "Tax: $80.00", "verified": True}]
    page_index, rect = locate(pdf, rows)["tax"]
    tax_line_rect = pymupdf.open(stream=pdf, filetype="pdf")[0].search_for("Tax: $80.00")[0]
    assert page_index == 0 and rect.intersects(tax_line_rect)


def test_pages_are_rendered_as_png_images():
    pdf = make_pdf(["Invoice Number: INV-1", "Total Amount Due: $100.00"])
    rows = [{"key": "invoice_number", "value": "INV-1", "evidence": None, "verified": True},
            {"key": "total", "value": "$100.00", "evidence": None, "verified": False}]
    images = render_pages(pdf, rows)
    assert len(images) == 1 and images[0][:8] == b"\x89PNG\r\n\x1a\n"


def test_a_value_that_is_not_on_the_page_is_simply_not_highlighted():
    pdf = make_pdf(["Invoice Number: INV-1"])
    rows = [{"key": "due_date", "value": "May 9, 2026", "evidence": None, "verified": False}]
    assert locate(pdf, rows) == {}
    assert len(render_pages(pdf, rows)) == 1


def test_a_guess_never_repaints_a_verified_value():
    from ui_helpers import highlight_plan, GREEN, AMBER
    rect = pymupdf.Rect(10, 10, 80, 22)
    found = {"invoice_date": (0, rect), "due_date": (0, pymupdf.Rect(rect))}
    plan = highlight_plan(found, {"invoice_date": True, "due_date": False})
    assert [color for _, _, color in plan] == [GREEN]


def test_an_unverified_value_elsewhere_is_still_marked():
    from ui_helpers import highlight_plan, GREEN, AMBER
    found = {"invoice_date": (0, pymupdf.Rect(10, 10, 80, 22)), "tax": (0, pymupdf.Rect(10, 100, 60, 112))}
    plan = highlight_plan(found, {"invoice_date": True, "tax": False})
    assert sorted(color for _, _, color in plan) == sorted([GREEN, AMBER])
