from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.ext.compiler import compiles
from pgvector.sqlalchemy import Vector
from app.core.config import settings
import logging

# Ensure SQLite compatibility for test fixtures
@compiles(Vector, "sqlite")
def compile_vector_sqlite(type_, compiler, **kw):
    return "TEXT"

logger = logging.getLogger(__name__)

# Normalize postgres:// to postgresql+psycopg:// if needed for Render/Neon compatibility
db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg://", 1)
elif db_url.startswith("postgresql://") and not db_url.startswith("postgresql+"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(
    db_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def init_db():
    """Initializes extensions like pgvector and creates all tables."""
    with engine.begin() as conn:
        try:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            logger.info("pgvector extension verified or created.")
        except Exception as e:
            logger.warning(f"Could not initialize pgvector extension directly: {e}")
        Base.metadata.create_all(bind=conn)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
