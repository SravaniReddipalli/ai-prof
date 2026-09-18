from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_password_hash
from app.models.models import (
    User, Space, Project, Material, DocumentChunk, Concept,
    ConceptMastery, MasteryHistory, Quiz, QuizQuestion, QuizAttempt,
    Recommendation, LearningEvent
)
from app.ai.openai_service import ai_service
from app.api.deps import oauth2_scheme
from app.core.security import decode_access_token

router = APIRouter(prefix="/demo", tags=["Demo Seeding"])

def verify_dev_or_admin(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """Strict security check: demo seeding is strictly development or admin-only."""
    if settings.ENVIRONMENT == "development":
        # In development mode, allow seeding or verify user if token provided
        try:
            payload = decode_access_token(token)
            if payload and payload.get("sub"):
                user = db.query(User).filter(User.id == payload["sub"]).first()
                if user:
                    return user
        except Exception:
            pass
        # Fallback to creating/fetching admin user
        admin = db.query(User).filter(User.role == "admin").first()
        return admin

    # In production, require valid token with admin role
    payload = decode_access_token(token)
    if not payload or not payload.get("sub"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user or user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Demo seeding is restricted to administrators")
    return user

@router.post("/seed")
def seed_demo_data(db: Session = Depends(get_db)):
    """
    Populates an end-to-end demo workspace for 'Database Management Systems'.
    Includes Admin and Student users, Spaces, Projects, processed Materials,
    Knowledge Chunks with vector embeddings, Concept Masteries, and Recommendations.
    """
    # 1. Create or get Admin & Student users
    admin_user = db.query(User).filter(User.email == "admin@aiprof.io").first()
    if not admin_user:
        admin_user = User(
            email="admin@aiprof.io",
            full_name="Prof. Alan Turing (Admin)",
            hashed_password=get_password_hash("admin123"),
            role="admin",
        )
        db.add(admin_user)

    student_user = db.query(User).filter(User.email == "student@aiprof.io").first()
    if not student_user:
        student_user = User(
            email="student@aiprof.io",
            full_name="Alex River (Student)",
            hashed_password=get_password_hash("student123"),
            role="user",
        )
        db.add(student_user)

    db.commit()
    db.refresh(admin_user)
    db.refresh(student_user)

    # 2. Create Space for student
    space = db.query(Space).filter(Space.user_id == student_user.id, Space.name == "Computer Science & Engineering").first()
    if not space:
        space = Space(
            user_id=student_user.id,
            name="Computer Science & Engineering",
            description="Foundational computing systems, algorithms, and distributed databases.",
            icon="database",
            color="indigo",
        )
        db.add(space)
        db.commit()
        db.refresh(space)

    # 3. Create Project
    project = db.query(Project).filter(Project.space_id == space.id, Project.name == "Database Management Systems (DBMS)").first()
    if not project:
        project = Project(
            space_id=space.id,
            user_id=student_user.id,
            name="Database Management Systems (DBMS)",
            description="Deep dive into relational schemas, normalization forms, transaction ACID properties, and B-Tree indexing.",
            learning_goal="Master relational normalization (1NF-BCNF), ACID transaction guarantees, and indexing internals for database design.",
        )
        db.add(project)
        db.commit()
        db.refresh(project)

    # 4. Create Material
    mat = db.query(Material).filter(Material.project_id == project.id).first()
    if not mat:
        mat = Material(
            project_id=project.id,
            user_id=student_user.id,
            title="DBMS Comprehensive Notes",
            filename="DBMS_Lecture_Notes.pdf",
            storage_key=f"projects/{project.id}/materials/dbms_notes.pdf",
            file_size_bytes=1048576,
            page_count=24,
            status="READY",
        )
        db.add(mat)
        db.commit()
        db.refresh(mat)

        # 5. Pre-populate Knowledge Chunks with Vector Embeddings
        chunks_data = [
            (
                1, 0,
                "Database normalization is the systematic approach of decomposing tables to eliminate data redundancy and undesirable anomalies (insertion, update, and deletion anomalies). First Normal Form (1NF) mandates atomic values and no repeating groups. Second Normal Form (2NF) requires 1NF and that all non-key attributes are fully functionally dependent on the primary key, eliminating partial dependencies.",
            ),
            (
                2, 1,
                "Third Normal Form (3NF) requires 2NF and the removal of transitive dependencies: every non-prime attribute must depend directly on the primary key, not through another non-prime attribute. Boyce-Codd Normal Form (BCNF) is a stricter variant where for every functional dependency X -> Y, X must be a superkey.",
            ),
            (
                7, 2,
                "Transactions ensure data integrity via the ACID properties: Atomicity (all-or-nothing execution), Consistency (preservation of database invariants), Isolation (transactions execute independently without interference), and Durability (committed changes persist across crashes). Isolation levels include Read Uncommitted, Read Committed, Repeatable Read, and Serializable.",
            ),
            (
                12, 3,
                "B-Tree and B+ Tree indexes are self-balancing search trees widely used in database engines. In a B+ Tree, all data records are stored in the leaf nodes, which are linked in a sequential doubly-linked list. This structure drastically optimizes range queries (e.g., WHERE age BETWEEN 20 AND 30) and reduces disk I/O to O(log N).",
            ),
            (
                18, 4,
                "Relational Joins combine rows from two or more tables based on a related column. Common physical join algorithms include Nested Loop Join (ideal for small inner tables or indexed lookups), Hash Join (efficient for large unsorted datasets via hash buckets in memory), and Sort-Merge Join (optimal when inputs are already sorted by join keys).",
            ),
        ]

        for page_num, idx, content in chunks_data:
            emb = ai_service.get_embedding(content, db=db, user_id=student_user.id, project_id=project.id)
            chunk = DocumentChunk(
                material_id=mat.id,
                project_id=project.id,
                page_number=page_num,
                chunk_index=idx,
                content=content,
                token_count=len(content) // 4,
                embedding=emb,
            )
            db.add(chunk)
        db.commit()

    # 6. Create Concepts & Masteries
    concepts_spec = [
        ("Normalization & Normal Forms", "1NF, 2NF, 3NF, BCNF and decomposition", 74.0, "improving"),
        ("Transactions & ACID Properties", "Concurrency, locks, atomicity and durability", 68.0, "stable"),
        ("B-Tree & Hash Indexing", "Tree balancing, leaf nodes, range queries", 42.0, "attention"),
        ("Relational Joins & Query Planning", "Nested loop, Hash join, Sort-merge algorithms", 85.0, "improving"),
    ]

    for c_name, c_desc, score, status_str in concepts_spec:
        c = db.query(Concept).filter(Concept.project_id == project.id, Concept.name == c_name).first()
        if not c:
            c = Concept(project_id=project.id, name=c_name, description=c_desc)
            db.add(c)
            db.commit()
            db.refresh(c)

        cm = db.query(ConceptMastery).filter(ConceptMastery.concept_id == c.id, ConceptMastery.user_id == student_user.id).first()
        if not cm:
            cm = ConceptMastery(
                concept_id=c.id,
                project_id=project.id,
                user_id=student_user.id,
                score=score,
                status=status_str,
                assessment_count=2,
                mistake_count=2 if score < 50 else 0,
                last_practiced_at=datetime.now(timezone.utc) - timedelta(hours=3),
            )
            db.add(cm)
            db.commit()

            # Add previous history entry to demonstrate growth
            prev_score = score - 8.0 if status_str == "improving" else score + 5.0
            hist = MasteryHistory(
                concept_id=c.id,
                project_id=project.id,
                user_id=student_user.id,
                previous_score=prev_score,
                new_score=score,
                trigger_event="SEED_INITIAL_QUIZ",
                created_at=datetime.now(timezone.utc) - timedelta(days=1),
            )
            db.add(hist)
            db.commit()

    # 7. Create targeted recommendation
    rec = db.query(Recommendation).filter(Recommendation.project_id == project.id, Recommendation.user_id == student_user.id).first()
    if not rec:
        idx_concept = db.query(Concept).filter(Concept.project_id == project.id, Concept.name == "B-Tree & Hash Indexing").first()
        rec = Recommendation(
            project_id=project.id,
            user_id=student_user.id,
            concept_id=idx_concept.id if idx_concept else None,
            action="Review B-Tree and B+ Tree range query mechanics on Page 12, then take an adaptive practice quiz.",
            reason="Your estimated mastery in Indexing is at 42% (requires attention). Reinforcing range query internals will boost your score.",
            priority="high",
            is_completed=False,
        )
        db.add(rec)
        db.commit()

    return {
        "status": "success",
        "message": "Demo data successfully seeded for Database Management Systems.",
        "credentials": {
            "admin": {"email": "admin@aiprof.io", "password": "admin123"},
            "student": {"email": "student@aiprof.io", "password": "student123"},
        },
        "project_id": project.id,
    }
