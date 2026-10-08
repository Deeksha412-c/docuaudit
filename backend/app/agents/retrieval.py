import uuid
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from app.core.config import settings

text_encoder = SentenceTransformer("BAAI/bge-small-en-v1.5")
client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
COLLECTION = "docuaudit_invoices"

def ensure_collection():
    if COLLECTION not in [c.name for c in client.get_collections().collections]:
        client.create_collection(COLLECTION, vectors_config=VectorParams(size=384, distance=Distance.COSINE))

def index_invoice(doc_id: str, chunks: list[str]):
    ensure_collection()
    vectors = text_encoder.encode(chunks).tolist()
    points = [
        PointStruct(
            id=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{doc_id}_{i}")),
            vector=v,
            payload={"doc_id": doc_id, "text": c},
        )
        for i, (c, v) in enumerate(zip(chunks, vectors))
    ]
    client.upsert(COLLECTION, points)

def retrieve(query: str, doc_id: str, k: int = 3) -> list[str]:
    qvec = text_encoder.encode(query).tolist()
    hits = client.query_points(
        COLLECTION,
        query=qvec,
        limit=k,
        query_filter={"must": [{"key": "doc_id", "match": {"value": doc_id}}]},
    ).points
    return [h.payload["text"] for h in hits]