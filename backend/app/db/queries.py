from sqlalchemy.orm import Session
from app.db.models import Document, DocStatus, ExtractionResult


def _norm(s) -> str:
    return str(s or "").strip().lower().rstrip(".")


def previously_seen_invoice_numbers(db: Session, doc_id: str, fields: dict) -> set[str]:
    """Invoice numbers already processed for the same vendor, excluding this document."""
    vendor = _norm(fields.get("vendor_name"))
    if not vendor:
        return set()

    rows = (
        db.query(ExtractionResult)
        .join(Document, Document.id == ExtractionResult.doc_id)
        .filter(ExtractionResult.doc_id != doc_id)
        .filter(Document.status == DocStatus.complete)
        .all()
    )

    seen = set()
    for r in rows:
        f = r.fields or {}
        if _norm(f.get("vendor_name")) == vendor and f.get("invoice_number"):
            seen.add(str(f["invoice_number"]))
    return seen