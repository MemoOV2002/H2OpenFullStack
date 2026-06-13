"""
Database configuration and connection
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Database URL - update with your PostgreSQL credentials
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://h2open_user:h2open_password@localhost:5432/h2open_db"
)

# Create SQLAlchemy engine
engine = create_engine(DATABASE_URL, echo=True)  # echo=True shows SQL queries in console

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


# Dependency to get database session
def get_db():
    """
    Database session dependency for FastAPI routes
    Usage: db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
