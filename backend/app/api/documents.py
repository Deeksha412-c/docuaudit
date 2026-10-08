import os
from fastapi import APIRouter, UploadFile, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.db.models import Document, DocStatus
from app.core.config import settings
from app.workers.tasks import process_document

router = APIRouter()

@router.post("/documents")
async def upload_document(file: UploadFile, db: Session = Depends(get_db)):
    doc = Document(filename=file.filename, file_path="", status=DocStatus.pending)
    db.add(doc)
    db.commit()
    db.refresh(doc)

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    stored_path = os.path.join(settings.UPLOAD_DIR, f"{doc.id}_{file.filename}")
    contents = await file.read()
    with open(stored_path, "wb") as f:
        f.write(contents)

    doc.file_path = stored_path
    db.commit()

    process_document.delay(doc.id, stored_path)
    return {"doc_id": doc.id, "status": doc.status}

@router.get("/documents/{doc_id}")
def get_document(doc_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        return {"error": "not found"}
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

@router.get("/documents")
def list_documents(db: Session = Depends(get_db)):
    docs = db.query(Document).order_by(Document.uploaded_at.desc()).all()
    return [{"doc_id": d.id, "filename": d.filename, "status": d.status} for d in docs]