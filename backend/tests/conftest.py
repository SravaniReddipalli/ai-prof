import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.database import Base, get_db
from app.core.security import get_password_hash, create_access_token
from app.models.models import User, Space, Project, Concept, Material, DocumentChunk

# In-memory test database with StaticPool to keep schema alive across connections
TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    """Yields a fresh in-memory database session for each test."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db_session):
    """FastAPI TestClient with overridden get_db dependency and patched init_db."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    # Patch init_db so the lifespan doesn't try to connect to real PostgreSQL
    from app.main import app
    app.dependency_overrides[get_db] = override_get_db
    with patch("app.main.init_db"):
        with TestClient(app) as test_client:
            yield test_client
    app.dependency_overrides.clear()

@pytest.fixture
def test_user(db_session):
    """Creates a regular test user."""
    user = User(
        email="learner@example.com",
        full_name="Test Learner",
        hashed_password=get_password_hash("password123"),
        role="user",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user

@pytest.fixture
def test_admin(db_session):
    """Creates an admin test user."""
    admin = User(
        email="admin@example.com",
        full_name="Test Admin",
        hashed_password=get_password_hash("admin123"),
        role="admin",
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin

@pytest.fixture
def user_token(test_user):
    return create_access_token({"sub": test_user.id, "email": test_user.email, "role": test_user.role})

@pytest.fixture
def admin_token(test_admin):
    return create_access_token({"sub": test_admin.id, "email": test_admin.email, "role": test_admin.role})

@pytest.fixture
def test_workspace(db_session, test_user):
    """Creates a Space, Project, Material, and Chunks for test_user."""
    space = Space(
        user_id=test_user.id,
        name="Computer Science",
        description="Core computing concepts",
    )
    db_session.add(space)
    db_session.commit()
    db_session.refresh(space)

    project = Project(
        space_id=space.id,
        user_id=test_user.id,
        name="Database Systems",
        learning_goal="Master normalization and transactions",
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    concept = Concept(
        project_id=project.id,
        name="Normalization",
        description="Eliminating redundancy",
    )
    db_session.add(concept)

    material = Material(
        project_id=project.id,
        user_id=test_user.id,
        title="DBMS Notes",
        filename="dbms.pdf",
        storage_key="test/dbms.pdf",
        page_count=10,
        status="READY",
    )
    db_session.add(material)
    db_session.commit()
    db_session.refresh(material)

    chunk0 = DocumentChunk(
        material_id=material.id,
        project_id=project.id,
        page_number=1,
        chunk_index=0,
        content="Normalization is the systematic process of organizing database tables to reduce redundancy, eliminate insertion and deletion anomalies, and prepare tables via 1NF and 2NF.",
        token_count=35,
    )
    chunk1 = DocumentChunk(
        material_id=material.id,
        project_id=project.id,
        page_number=2,
        chunk_index=1,
        content="Third Normal Form (3NF) requires 2NF and the removal of transitive dependencies where non-key attributes must depend only on the primary key. 3NF is used to prevent update anomalies while maintaining lossless joins.",
        token_count=40,
    )
    chunk2 = DocumentChunk(
        material_id=material.id,
        project_id=project.id,
        page_number=12,
        chunk_index=2,
        content="B-Tree and B+ Tree indexes drastically speed up range queries by storing sorted data keys in leaf nodes connected by pointers.",
        token_count=30,
    )
    db_session.add_all([chunk0, chunk1, chunk2])
    db_session.commit()

    return {
        "space": space,
        "project": project,
        "concept": concept,
        "material": material,
        "chunks": [chunk0, chunk1, chunk2],
    }
