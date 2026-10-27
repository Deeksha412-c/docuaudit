import os, sys, tempfile, types, uuid

UPLOADS = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = "sqlite://"            # never touch the real database in tests
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ["UPLOAD_DIR"] = UPLOADS
os.environ["DOCUAUDIT_SECRET"] = "a-secret-used-only-in-the-tests"
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))

# the real task module would load the models; here only the call that queues a job matters
queued = []
fake_tasks = types.ModuleType("app.workers.tasks")
fake_tasks.process_document = types.SimpleNamespace(delay=lambda doc_id, path: queued.append((doc_id, path)))
sys.modules["app.workers.tasks"] = fake_tasks

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.auth import router as auth_router
from app.api.documents import router as documents_router
from app.db.models import Base
from app.db.session import get_db

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)


def override_db():
    db = Session()
    try:
        yield db
    finally:
        db.close()


app = FastAPI()
app.include_router(auth_router)
app.include_router(documents_router)
app.dependency_overrides[get_db] = override_db
client = TestClient(app)

PDF = b"%PDF-1.4\n% a tiny stand-in for an invoice\n"


def new_user(password="a long enough password"):
    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    response = client.post("/auth/signup", json={"email": email, "password": password, "name": "Test"})
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}, email


def upload(headers, name="invoice.pdf", data=PDF):
    return client.post("/documents", files={"file": (name, data, "application/pdf")}, headers=headers)


# --- accounts ---------------------------------------------------------------------------------

def test_signup_returns_a_token_and_never_the_password():
    r = client.post("/auth/signup", json={"email": "New.User@Example.com", "password": "long enough pw", "name": " Asha "})
    body = r.json()
    assert r.status_code == 201 and body["access_token"]
    assert body["user"]["email"] == "new.user@example.com" and body["user"]["name"] == "Asha"
    assert "password" not in str(body).lower().replace("access_token", "")


def test_an_email_can_only_be_used_once_whatever_its_case():
    client.post("/auth/signup", json={"email": "dup@example.com", "password": "long enough pw"})
    r = client.post("/auth/signup", json={"email": "DUP@example.com", "password": "another long pw"})
    assert r.status_code == 409


def test_bad_signups_are_rejected():
    assert client.post("/auth/signup", json={"email": "not-an-email", "password": "long enough pw"}).status_code == 400
    assert client.post("/auth/signup", json={"email": "a@example.com", "password": "short"}).status_code == 400


def test_login_works_with_the_right_password_only():
    _, email = new_user("my real password")
    ok = client.post("/auth/login", data={"username": email, "password": "my real password"})
    assert ok.status_code == 200 and ok.json()["access_token"]
    wrong = client.post("/auth/login", data={"username": email, "password": "not my password"})
    unknown = client.post("/auth/login", data={"username": "nobody@example.com", "password": "whatever long"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()            # no hint about which emails have accounts


def test_me_needs_a_valid_token():
    headers, email = new_user()
    assert client.get("/auth/me", headers=headers).json()["email"] == email
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


# --- documents belong to their owner ------------------------------------------------------------

def test_documents_need_a_login():
    assert client.get("/documents").status_code == 401
    assert client.post("/documents", files={"file": ("a.pdf", PDF, "application/pdf")}).status_code == 401


def test_a_user_sees_only_their_own_documents():
    alice, _ = new_user()
    bob, _ = new_user()
    doc_id = upload(alice).json()["doc_id"]

    assert [d["doc_id"] for d in client.get("/documents", headers=alice).json()] == [doc_id]
    assert client.get("/documents", headers=bob).json() == []
    assert client.get(f"/documents/{doc_id}", headers=alice).status_code == 200
    assert client.get(f"/documents/{doc_id}", headers=bob).status_code == 404
    assert client.get(f"/documents/{doc_id}/file", headers=bob).status_code == 404


def test_the_owner_can_download_their_file_back():
    alice, _ = new_user()
    doc_id = upload(alice).json()["doc_id"]
    r = client.get(f"/documents/{doc_id}/file", headers=alice)
    assert r.status_code == 200 and r.content == PDF


def test_an_upload_is_queued_for_processing():
    alice, _ = new_user()
    doc_id = upload(alice).json()["doc_id"]
    assert queued[-1][0] == doc_id and os.path.isfile(queued[-1][1])


def test_only_pdfs_are_accepted():
    alice, _ = new_user()
    assert upload(alice, "notes.pdf", b"just some text").status_code == 400


def test_a_hostile_file_name_cannot_escape_the_upload_folder():
    alice, _ = new_user()
    upload(alice, "../../evil.pdf")
    upload(alice, "..\\..\\evil2.pdf")
    for _, path in queued[-2:]:
        assert os.path.realpath(os.path.dirname(path)) == os.path.realpath(UPLOADS)
