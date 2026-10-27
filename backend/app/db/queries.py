from sqlalchemy.orm import Session
from app.db.models import Document, DocStatus, ExtractionResult


def _norm(s) -> str:
    return str(s or "").strip().lower().rstrip(".")


def previously_seen_invoice_numbers(db: Session, doc_id: str, fields: dict) -> set[str]:
    """Invoice numbers already processed for the same vendor, for the same user, excluding this document."""
    vendor = _norm(fields.get("vendor_name"))
    if not vendor:
        return set()

    current = db.query(Document).filter(Document.id == doc_id).first()
    owner = current.user_id if current else None
    same_owner = Document.user_id.is_(None) if owner is None else Document.user_id == owner

    rows = (
        db.query(ExtractionResult)
        .join(Document, Document.id == ExtractionResult.doc_id)
        .filter(ExtractionResult.doc_id != doc_id)
        .filter(Document.status.in_([DocStatus.complete, DocStatus.needs_review]))
        .filter(same_owner)
        .all()
    )

    seen = set()
    for r in rows:
        f = r.fields or {}
        if _norm(f.get("vendor_name")) == vendor and f.get("invoice_number"):
            seen.add(str(f["invoice_number"]))
    return seen
