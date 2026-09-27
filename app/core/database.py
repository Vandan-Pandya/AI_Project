"""
Database engine and session management for PostgreSQL & Supabase.
Uses SQLAlchemy 2.0 with serverless-resilient connection pooling and session dependency injection.
"""

from __future__ import annotations
import os
from typing import Generator
from fastapi import HTTPException, status
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from app.core.config import DATABASE_URL

# Declarative Base for ORM Models
Base = declarative_base()

# Engine & Session initialization with empty-URL safety
is_configured = bool(DATABASE_URL)
engine = None
SessionLocal = None

if is_configured:
    is_sqlite = DATABASE_URL.startswith("sqlite")
    engine_kwargs = {"echo": False}

    # Detect Vercel or cloud serverless container
    is_serverless = os.getenv("VERCEL") == "1" or bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME"))

    if not is_sqlite:
        if is_serverless or "pooler.supabase.com" in DATABASE_URL:
            # Serverless / Pooler Mode: Use NullPool to avoid connection leaks across cold starts
            from sqlalchemy.pool import NullPool
            engine_kwargs.update({
                "poolclass": NullPool,
                "pool_pre_ping": True,
            })
        else:
            engine_kwargs.update({
                "pool_pre_ping": True,
                "pool_recycle": 300,
                "pool_size": 5,
                "max_overflow": 10,
            })

    engine = create_engine(DATABASE_URL, **engine_kwargs)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency yielding a request-scoped database session.
    Raises HTTP 503 if DATABASE_URL is not yet configured.
    """
    if SessionLocal is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection is not configured. Please set the DATABASE_URL environment variable."
        )
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Creates all tables in PostgreSQL if they do not exist.
    Safely skips if DATABASE_URL is not provided.
    """
    if engine is None:
        print("[EduMentor] Notice: DATABASE_URL is not set. Skipping table initialization.")
        return
    Base.metadata.create_all(bind=engine)
