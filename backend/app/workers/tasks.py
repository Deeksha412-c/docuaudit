from app.workers.celery_app import celery_app
from app.db.session import SessionLocal
from app.db.models import Document, DocStatus, ExtractionResult, ComplianceFlag, AuditLog
from app.graph.pipeline import pipeline
from app.agents.ingestion import ingest_invoice, full_text
from app.agents.retrieval import index_invoice

@celery_app.task
def process_document(doc_id: str, pdf_path: str):
    db = SessionLocal()
    doc = db.query(Document).get(doc_id)
    doc.status = DocStatus.processing
    db.commit()

    try:
        pages = ingest_invoice(pdf_path)
        text = full_text(pages)
        index_invoice(doc_id, [text])

        result = pipeline.invoke({"doc_id": doc_id, "source_text": text})

        db.add(ExtractionResult(doc_id=doc_id, fields=result["fields"]))
        db.add(ComplianceFlag(doc_id=doc_id, pii_entities=result["compliance"]["pii_entities"],
                               flags=result["compliance"]["flags"], risk_level=result["compliance"]["risk_level"]))
        db.add(AuditLog(doc_id=doc_id, per_field=result["audit"]["per_field"],
                         faithfulness_rate=result["audit"]["faithfulness_rate"], model_versions={}))
        doc.status = DocStatus.complete
    except Exception as e:
        doc.status = DocStatus.failed
        print(f"Pipeline failed for {doc_id}: {e}")
    finally:
        db.commit()
        db.close()