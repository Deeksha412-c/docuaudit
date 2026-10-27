from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.documents import router as documents_router
from app.db.models import Base
from app.db.session import engine

app = FastAPI(title="DocuAudit — Invoice Edition")
Base.metadata.create_all(bind=engine)
app.include_router(auth_router)
app.include_router(documents_router)


@app.get("/health")
def health():
    return {"status": "ok"}
