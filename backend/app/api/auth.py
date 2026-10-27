import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.db.models import User
from app.db.session import get_db

SECRET = settings.DOCUAUDIT_SECRET
if len(SECRET) < 16:
    raise RuntimeError(
        "DOCUAUDIT_SECRET is missing or too short. Add a random value of at least 16 characters "
        "to your .env file (see .env.example)."
    )

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_DUMMY_HASH = hash_password("a-password-nobody-uses")     # keeps login timing similar for unknown emails


class SignupIn(BaseModel):
    email: str
    password: str
    name: str = ""


def _public(user: User) -> dict:
    return {"id": user.id, "email": user.email, "name": user.name or ""}


def _session(user: User) -> dict:
    return {"access_token": create_token(user.id, SECRET), "token_type": "bearer", "user": _public(user)}


def get_current_user(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> User:
    user_id = decode_token(token, SECRET)
    user = db.query(User).filter(User.id == user_id).first() if user_id else None
    if user is None:
        raise HTTPException(401, "Your session is not valid. Please sign in again.",
                            headers={"WWW-Authenticate": "Bearer"})
    return user


@router.post("/signup", status_code=201)
def signup(body: SignupIn, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if len(email) > 254 or not EMAIL.match(email):
        raise HTTPException(400, "Enter a valid email address.")
    if len(body.password) < 8:
        raise HTTPException(400, "Use at least 8 characters for the password.")
    if len(body.password) > 128:
        raise HTTPException(400, "The password is too long (128 characters at most).")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "An account with this email already exists.")

    user = User(email=email, name=body.name.strip()[:80], password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An account with this email already exists.")
    db.refresh(user)
    return _session(user)


@router.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form.username.strip().lower()).first()
    password_ok = verify_password(form.password, user.password_hash if user else _DUMMY_HASH)
    if user is None or not password_ok:
        raise HTTPException(401, "Incorrect email or password.")
    return _session(user)


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return _public(user)
