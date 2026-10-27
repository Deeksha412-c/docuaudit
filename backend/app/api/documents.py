import os
import re

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.config import settings
from app.db.models import DocStatus, Document, User
from app.db.session import get_db
from app.workers.tasks import process_document

router = APIRouter()
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _display_name(name) -> str:
    """The file name without any folder part, for showing in the UI."""
    return os.path.basename((name or "invoice.pdf").replace("\\", "/"))[:200] or "invoice.pdf"


def _stored_name(name: str) -> str:
    """A name that is safe to use on disk."""
    return re.sub(r"[^A-Za-z0-9._-]", "_", name) or "invoice.pdf"


def _owned(db: Session, doc_id: str, user: User) -> Document:
    doc = db.query(Document).filter(Document.id == doc_id, Document.user_id == user.id).first()
    if doc is None:
        raise HTTPException(404, "Document not found.")
    return doc


@router.post("/documents")
async def upload_document(file: UploadFile, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    contents = await file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "The file is larger than 10 MB.")
    if not contents.startswith(b"%PDF"):
        raise HTTPException(400, "Only PDF files are accepted.")

    name = _display_name(file.filename)
    doc = Document(user_id=user.id, filename=name, file_path="", status=DocStatus.pending)
    db.add(doc)
    db.commit()
    db.refresh(doc)

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    stored_path = os.path.join(settings.UPLOAD_DIR, f"{doc.id}_{_stored_name(name)}")
    with open(stored_path, "wb") as f:
        f.write(contents)

    doc.file_path = stored_path
    db.commit()

    process_document.delay(doc.id, stored_path)
    return {"doc_id": doc.id, "status": doc.status}


@router.get("/documents/{doc_id}")
def get_document(doc_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    doc = _owned(db, doc_id, user)
    return {
        "doc_id": doc.id,
        "filename": doc.filename,
        "status": doc.status,
        "extraction": doc.extraction.fields if doc.extraction else None,
        "compliance": {"flags": doc.compliance.flags, "risk_level": doc.compliance.risk_level,
                       "pii_entities": doc.compliance.pii_entities} if doc.compliance else None,
        "audit": {"faithfulness_rate": doc.audit.faithfulness_rate,
                  "per_field": doc.audit.per_field} if doc.audit else None,
    }


@router.get("/documents/{doc_id}/file")
def get_document_file(doc_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    doc = _owned(db, doc_id, user)
    if not doc.file_path or not os.path.isfile(doc.file_path):
        raise HTTPException(404, "The file is not available.")
    return FileResponse(doc.file_path, media_type="application/pdf", filename=doc.filename)


@router.get("/documents")
def list_documents(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    docs = (db.query(Document).filter(Document.user_id == user.id)
            .order_by(Document.uploaded_at.desc()).all())
    return [{"doc_id": d.id, "filename": d.filename, "status": d.status,
             "uploaded_at": d.uploaded_at.isoformat() if d.uploaded_at else None} for d in docs]
