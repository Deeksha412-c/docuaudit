import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.models import Base, Document, DocStatus, ExtractionResult
from app.db.queries import previously_seen_invoice_numbers


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def add_doc(db, doc_id, fields, status=DocStatus.complete):
    db.add(Document(id=doc_id, filename=f"{doc_id}.pdf", file_path="x", status=status))
    db.add(ExtractionResult(doc_id=doc_id, fields=fields))
    db.commit()


def test_same_vendor_same_number_is_seen(db):
    add_doc(db, "a", {"invoice_number": "INV-1", "vendor_name": "Acme Supplies Ltd."})
    seen = previously_seen_invoice_numbers(db, "b", {"vendor_name": "acme supplies ltd"})
    assert "INV-1" in seen


def test_different_vendor_is_not_seen(db):
    add_doc(db, "a", {"invoice_number": "INV-1", "vendor_name": "Acme Supplies Ltd."})
    seen = previously_seen_invoice_numbers(db, "b", {"vendor_name": "Nova Print Works"})
    assert seen == set()


def test_current_document_is_excluded(db):
    add_doc(db, "a", {"invoice_number": "INV-1", "vendor_name": "Acme"})
    assert previously_seen_invoice_numbers(db, "a", {"vendor_name": "Acme"}) == set()


def test_failed_documents_are_ignored(db):
    add_doc(db, "a", {"invoice_number": "INV-1", "vendor_name": "Acme"}, status=DocStatus.failed)
    assert previously_seen_invoice_numbers(db, "b", {"vendor_name": "Acme"}) == set()


def test_missing_vendor_returns_empty(db):
    add_doc(db, "a", {"invoice_number": "INV-1", "vendor_name": "Acme"})
    assert previously_seen_invoice_numbers(db, "b", {"vendor_name": ""}) == set()