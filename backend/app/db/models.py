from sqlalchemy import Column, String, Float, DateTime, JSON, ForeignKey, Enum
from sqlalchemy.orm import declarative_base, relationship
import datetime, enum, uuid

Base = declarative_base()

class DocStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    complete = "complete"
    needs_review = "needs_review"
    failed = "failed"

class Document(Base):
    __tablename__ = "documents"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)   # where the source PDF actually lives on disk
    status = Column(Enum(DocStatus), default=DocStatus.pending)
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)

    extraction = relationship("ExtractionResult", back_populates="document", uselist=False)
    compliance = relationship("ComplianceFlag", back_populates="document", uselist=False)
    audit = relationship("AuditLog", back_populates="document", uselist=False)

class ExtractionResult(Base):
    __tablename__ = "extraction_results"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    doc_id = Column(String, ForeignKey("documents.id"))
    fields = Column(JSON)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    document = relationship("Document", back_populates="extraction")

class ComplianceFlag(Base):
    __tablename__ = "compliance_flags"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    doc_id = Column(String, ForeignKey("documents.id"))
    pii_entities = Column(JSON)
    flags = Column(JSON)
    risk_level = Column(String)
    document = relationship("Document", back_populates="compliance")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    doc_id = Column(String, ForeignKey("documents.id"))
    per_field = Column(JSON)
    faithfulness_rate = Column(Float)
    model_versions = Column(JSON)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    document = relationship("Document", back_populates="audit")