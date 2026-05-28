"""
SQLAlchemy database connection and session management.

Design notes:
- create_engine with pool_pre_ping=True: tests connections before use,
  prevents stale connection errors after idle periods
  (relevant on AWS RDS where connections may be dropped).
- SessionLocal is a factory; we create a fresh session per request via
  the get_db() FastAPI dependency, then close it cleanly.
- Base is the declarative base all ORM models inherit from.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=settings.ENVIRONMENT == "development",
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """
    FastAPI dependency that provides a database session per request.
    Usage in endpoints:
        def endpoint(db: Session = Depends(get_db)): ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
