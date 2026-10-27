"""Helpers for the UI: labels, status mapping and invoice highlighting.

No Streamlit imports here, so everything in this file can be unit-tested.
"""

FIELD_ORDER = ["invoice_number", "invoice_date", "vendor_name", "due_date", "subtotal", "tax", "total"]

FIELD_LABELS = {
    "invoice_number": "Invoice number",
    "invoice_date": "Invoice date",
    "vendor_name": "Vendor",
    "due_date": "Due date",
    "subtotal": "Subtotal",
    "tax": "Tax",
    "total": "Total",
}

FLAG_LABELS = {
    "duplicate_invoice_number": "Possible duplicate",
    "total_does_not_match_subtotal_plus_tax": "Total does not add up",
    "amount_over_policy_threshold": "Above the amount threshold",
    "amount_fields_unparseable": "An amount could not be read",
}

REASON_LABELS = {
    "empty": "Nothing was found",
    "not_in_source": "Not found in the invoice",
    "label_mismatch": "Not next to the right label",
    "not_a_date": "Not a date",
    "not_an_amount": "Not an amount",
    "no_digits": "Has no digits",
    "is_a_label": "Looks like a label, not a value",
}

STATUS_PILLS = {
    "complete": ("Verified", "ok"),
    "needs_review": ("Needs review", "warn"),
    "failed": ("Failed", "bad"),
    "pending": ("Waiting", "muted"),
    "processing": ("Processing", "muted"),
}

GREEN = (0.13, 0.55, 0.35)
AMBER = (0.85, 0.52, 0.10)


def status_pill(status):
    return STATUS_PILLS.get(status, (str(status), "muted"))


def risk_pill(level):
    return ("High risk", "bad") if level == "high" else ("Low risk", "ok")


def format_time(iso):
    """'2026-10-20T14:03:11.123' -> '2026-10-20 14:03'."""
    return str(iso)[:16].replace("T", " ") if iso else ""


def flag_label(flag):
    return FLAG_LABELS.get(flag, str(flag).replace("_", " ").capitalize())


def why_not(audit_entry):
    """A plain-language reason a field was not verified."""
    reason = audit_entry.get("reason")
    if reason:
        return REASON_LABELS.get(reason, reason.replace("_", " "))
    if audit_entry.get("nli_label") == "contradiction":
        return "The invoice line contradicts this value"
    return "The invoice line does not clearly support this value"


def field_rows(result):
    """One row per field, in a fixed order, from the API response."""
    fields = result.get("extraction") or {}
    audit = (result.get("audit") or {}).get("per_field") or {}
    rows = []
    for key in FIELD_ORDER:
        entry = audit.get(key, {})
        verified = bool(entry.get("supported"))
        rows.append({
            "key": key,
            "label": FIELD_LABELS[key],
            "value": str(fields.get(key) or ""),
            "verified": verified,
            "evidence": entry.get("evidence"),
            "note": None if verified else why_not(entry),
        })
    return rows


def _value_rect(page, value, evidence):
    rects = page.search_for(value)
    if not rects:
        return None
    if len(rects) > 1 and evidence:          # the value appears more than once: prefer the evidence line
        lines = page.search_for(evidence)
        inside = [r for r in rects if any(r.intersects(line) for line in lines)]
        if inside:
            return inside[0]
    return rects[0]


def locate(pdf_bytes, rows, max_pages=3):
    """Where each value sits on the invoice: {field key: (page index, rectangle)}."""
    import pymupdf
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    found = {}
    try:
        for page_index in range(min(len(doc), max_pages)):
            page = doc[page_index]
            for row in rows:
                if row["key"] in found or not row["value"]:
                    continue
                rect = _value_rect(page, row["value"], row.get("evidence"))
                if rect is not None:
                    found[row["key"]] = (page_index, rect)
    finally:
        doc.close()
    return found


def highlight_plan(found, verified):
    """Which boxes to draw: [(page index, rectangle, colour)]. Verified values are drawn first, and a
    guess that sits on the same text as a verified value is skipped, so it cannot repaint it."""
    plan = []
    for key, (page, rect) in found.items():
        if verified.get(key):
            plan.append((page, rect, GREEN))
    for key, (page, rect) in found.items():
        if verified.get(key):
            continue
        if any(p == page and rect.intersects(r) for p, r, _ in plan):
            continue
        plan.append((page, rect, AMBER))
    return plan


def render_pages(pdf_bytes, rows, max_pages=3, zoom=1.5):
    """PNG images of the invoice pages, with verified values in green and the rest in amber."""
    import pymupdf
    found = locate(pdf_bytes, rows, max_pages)
    plan = highlight_plan(found, {row["key"]: row["verified"] for row in rows})
    doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    images = []
    try:
        for page_index in range(min(len(doc), max_pages)):
            page = doc[page_index]
            for p, rect, color in plan:
                if p != page_index:
                    continue
                box = pymupdf.Rect(rect.x0 - 2, rect.y0 - 1, rect.x1 + 2, rect.y1 + 1)
                page.draw_rect(box, color=color, fill=color, fill_opacity=0.18, width=1.2)
            images.append(page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom)).tobytes("png"))
    finally:
        doc.close()
    return images
