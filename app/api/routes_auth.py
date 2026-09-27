"""
Authentication Router (3 Endpoints: Register, Login, Me).
Handles user registration, authentication, JWT tokens, and database transaction safety.
"""

from __future__ import annotations
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from app.core.database import get_db
from app.core import security
from app.models import models
from app.schemas import schemas

router = APIRouter(prefix="/auth", tags=["Authentication"])
security_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> models.User:
    """Dependency extracting and verifying the JWT token."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = security.decode_access_token(credentials.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        user_uuid = uuid.UUID(payload["sub"])
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token subject format"
        )
    
    try:
        user = db.query(models.User).options(
            joinedload(models.User.student_profile),
            joinedload(models.User.teacher_profile)
        ).filter(models.User.user_id == user_uuid).first()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service temporarily unavailable"
        )

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User account not found")
    
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account has been deactivated")
    
    return user


@router.post(
    "/register",
    response_model=schemas.TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="1. Register user"
)
def register(req: schemas.UserRegisterRequest, db: Session = Depends(get_db)):
    """Registers a new student or teacher and creates their linked profile record with transaction safety."""
    clean_email = req.email.lower().strip()
    
    try:
        existing = db.query(models.User).filter(models.User.email == clean_email).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is already registered")
        
        new_user = models.User(
            email=clean_email,
            password_hash=security.hash_password(req.password),
            role=req.role,
            is_active=True,
        )
        db.add(new_user)
        db.flush()

        if req.role == "student":
            student_profile = models.Student(
                student_id=new_user.user_id,
                full_name=req.full_name.strip(),
                grade=req.grade.strip() if req.grade else "Grade 10",
            )
            db.add(student_profile)
        elif req.role == "teacher":
            teacher_profile = models.Teacher(
                teacher_id=new_user.user_id,
                full_name=req.full_name.strip(),
                department=req.department.strip() if req.department else "General",
            )
            db.add(teacher_profile)

        db.commit()
        db.refresh(new_user)

    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An account with this email already exists")
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Registration failed: {str(exc)}")

    token = security.create_access_token(
        data={"sub": str(new_user.user_id), "role": new_user.role, "email": new_user.email}
    )

    return schemas.TokenResponse(
        access_token=token,
        token_type="bearer",
        user=schemas.UserOut.model_validate(new_user)
    )


@router.post("/login", response_model=schemas.TokenResponse, summary="2. Login user")
def login(req: schemas.UserLoginRequest, db: Session = Depends(get_db)):
    """Authenticates email and password and issues a JWT token."""
    clean_email = req.email.lower().strip()
    
    try:
        user = db.query(models.User).options(
            joinedload(models.User.student_profile),
            joinedload(models.User.teacher_profile)
        ).filter(models.User.email == clean_email).first()
    except SQLAlchemyError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database service temporarily unavailable")

    if not user or not security.verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account has been deactivated")

    token = security.create_access_token(
        data={"sub": str(user.user_id), "role": user.role, "email": user.email}
    )

    return schemas.TokenResponse(
        access_token=token,
        token_type="bearer",
        user=schemas.UserOut.model_validate(user)
    )


@router.get("/me", response_model=schemas.UserOut, summary="3. Get current user profile")
def get_me(current_user: models.User = Depends(get_current_user)):
    """Returns profile details of the authenticated user."""
    return schemas.UserOut.model_validate(current_user)
