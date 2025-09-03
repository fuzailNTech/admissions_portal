from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.settings import DATABASE_URL


# Connect to the PostgreSQL database
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for our models
Base = declarative_base()


# Dependency to get a new session for each request
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
