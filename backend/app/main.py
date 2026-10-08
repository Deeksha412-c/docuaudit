from fastapi import FastAPI
from app.api.documents import router as documents_router
from app.db.session import engine
from app.db.models import Base

app = FastAPI(title="DocuAudit — Invoice Edition")
Base.metadata.create_all(bind=engine)
app.include_router(documents_router)

@app.get("/health")
def health():
    return {"status": "ok"}