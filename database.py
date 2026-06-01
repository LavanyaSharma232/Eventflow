import os
from sqlalchemy import create_engine
from dotenv import load_dotenv
from sqlalchemy.orm import sessionmaker, declarative_base

# Load this from your .env file in production!
# Format: postgresql://user:password@localhost/dbname
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()