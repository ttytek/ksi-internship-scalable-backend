from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ksi.api.deps import get_db
from ksi.domain.entities import User
from ksi.schemas.user import UserCreate, UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, db: Session = Depends(get_db)) -> User:
    """Tworzy użytkownika. Jeśli username zajęty — 409."""
    existing = db.query(User).filter(User.username == body.username).one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username {body.username!r} already taken",
        )
    user = User(username=body.username)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=UserOut)
def login_or_register(body: UserCreate, db: Session = Depends(get_db)) -> User:
    """
    Proste „logowanie” bez hasła: zwraca istniejącego użytkownika
    albo tworzy nowego o podanym username.
    """
    user = db.query(User).filter(User.username == body.username).one_or_none()
    if user is None:
        user = User(username=body.username)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: UUID, db: Session = Depends(get_db)) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user
