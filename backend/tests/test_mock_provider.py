import pytest
import math
from unittest.mock import patch
from app.core.config import settings
from app.ai.openai_service import AIService, generate_mock_embedding, ai_service
from app.services.reembed_service import reembed_all_chunks
from app.services.learning_service import LearningService, GeneratedQuizPayload
from app.schemas.schemas import OpenEndedEvaluation
from app.models.models import DocumentChunk, AIUsage, ConceptMastery

def test_mock_mode_zero_openai_calls(monkeypatch, db_session):
    """
    Verifies that when AI_PROVIDER=mock, AIService initializes with client=None
    and performs embedding, chat, and structured generation with zero OpenAI network calls,
    even if OPENAI_API_KEY is populated.
    """
    monkeypatch.setattr(settings, "AI_PROVIDER", "mock")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-mock-dummy-key-should-never-be-called")

    # Re-initialize AIService to simulate app startup with these settings
    test_ai = AIService()
    assert test_ai.provider == "mock"
    assert test_ai.client is None

    # Patch OpenAI library to ensure that any network instantiation would fail immediately
    with patch("openai.OpenAI", side_effect=RuntimeError("NETWORK CALL FORBIDDEN")):
        # 1. Embedding generation
        emb = test_ai.get_embedding("Test text for embedding", db=db_session)
        assert isinstance(emb, list)
        assert len(emb) == 1536
        assert math.isclose(math.sqrt(sum(x * x for x in emb)), 1.0, rel_tol=1e-3)

        # 2. Chat generation (grounded)
        sys_prompt = "--- PROJECT MATERIALS EVIDENCE ---\n[Source 1: Test Doc | Page: 1]\nCellular respiration produces ATP.\n----------------------------------"
        chat_reply = test_ai.generate_chat(
            system_prompt=sys_prompt,
            messages=[{"role": "user", "content": "How does respiration produce ATP?"}],
            db=db_session,
            feature="tutor"
        )
        assert "cellular respiration" in chat_reply.lower() or "atp" in chat_reply.lower()
        assert "Source: Test Doc — Page 1" in chat_reply

        # 3. Structured generation (quiz)
        quiz = test_ai.generate_structured(
            system_prompt="Target Concepts: Cellular Respiration, Glycolysis\nDifficulty Level: medium",
            user_prompt="Context: ATP synthesis mechanics.",
            response_schema=GeneratedQuizPayload,
            db=db_session,
            feature="quiz_generation"
        )
        assert isinstance(quiz, GeneratedQuizPayload)
        assert len(quiz.questions) == 4

    # Verify AI observability was logged in DB
    usage_logs = db_session.query(AIUsage).all()
    assert len(usage_logs) >= 3
    for log in usage_logs:
        assert log.success is True

def test_deterministic_lexical_embedding_properties():
    """
    Verifies the deterministic lexical/term-feature retrieval embedding:
    - 1536 dimensions, L2 normalized
    - Strictly deterministic
    - Higher cosine similarity for overlapping/related queries than unrelated queries
    """
    doc_text = "Third Normal Form (3NF) requires 2NF and the removal of transitive dependencies."
    related_query = "What is Third Normal Form 3NF?"
    unrelated_query = "What is the capital of France and European history?"

    emb_doc = generate_mock_embedding(doc_text)
    emb_doc_repeat = generate_mock_embedding(doc_text)
    emb_rel = generate_mock_embedding(related_query)
    emb_unrel = generate_mock_embedding(unrelated_query)

    # 1. Dimensionality & normalization
    assert len(emb_doc) == 1536
    norm = math.sqrt(sum(x * x for x in emb_doc))
    assert math.isclose(norm, 1.0, rel_tol=1e-3)

    # 2. Strict determinism
    assert emb_doc == emb_doc_repeat

    # 3. Term/concept overlap similarity
    sim_rel = sum(a * b for a, b in zip(emb_doc, emb_rel))
    sim_unrel = sum(a * b for a, b in zip(emb_doc, emb_unrel))

    assert sim_rel > sim_unrel
    assert sim_rel > 0.35  # Strong overlap
    assert sim_unrel < 0.15  # Negligible / random collision overlap

def test_reembed_service(db_session, test_workspace):
    """
    Tests the safe re-embedding path for existing document chunks.
    """
    chunks = test_workspace["chunks"]
    # Corrupt or set old-style dummy embeddings
    for c in chunks:
        c.embedding = [0.0] * 1536
    db_session.commit()

    # Run re-embedding service
    result = reembed_all_chunks(db_session, project_id=test_workspace["project"].id)
    assert result["total_chunks"] == len(chunks)
    assert result["reembedded"] == len(chunks)
    assert result["status"] == "completed"

    # Verify embeddings are updated and match generate_mock_embedding
    for c in chunks:
        db_session.refresh(c)
        expected = generate_mock_embedding(c.content)
        diff = sum(abs(a - b) for a, b in zip(list(c.embedding), expected))
        assert diff < 1e-4

def test_dynamic_quiz_generation_no_database_hardcoding(db_session, test_user):
    """
    Verifies dynamic quiz generation creates questions tailored to target concepts
    (e.g. Photosynthesis, Chloroplast) without hardcoding database terms (concurrency, B-Tree, etc.).
    """
    from app.models.models import Space, Project, Concept
    space = Space(user_id=test_user.id, name="Biology Space")
    db_session.add(space)
    db_session.commit()

    project = Project(
        space_id=space.id,
        user_id=test_user.id,
        name="Plant Biology",
        learning_goal="Master cellular biology"
    )
    db_session.add(project)
    db_session.commit()

    c1 = Concept(project_id=project.id, name="Photosynthesis", description="Light reactions")
    c2 = Concept(project_id=project.id, name="Chloroplast", description="Organelle")
    db_session.add_all([c1, c2])
    db_session.commit()

    quiz_res = LearningService.generate_adaptive_quiz(
        project_id=project.id,
        user_id=test_user.id,
        db=db_session
    )

    assert quiz_res.title is not None
    assert len(quiz_res.questions) == 4

    all_questions_text = " ".join(q.question for q in quiz_res.questions)
    # Must mention biological concepts
    assert "photosynthesis" in all_questions_text.lower() or "chloroplast" in all_questions_text.lower()

    # Must NOT contain hardcoded database terms
    assert "b-tree" not in all_questions_text.lower()
    assert "concurrency" not in all_questions_text.lower()
    assert "disk i/o" not in all_questions_text.lower()
    assert "table scan" not in all_questions_text.lower()

def test_mock_open_ended_grading():
    """
    Verifies deterministic grading of open-ended quiz responses:
    - Empty or non-answers get 0
    - Substantive answers covering concepts receive credit
    """
    sys_prompt = "Reference Answer: Normalization decomposes tables to remove anomalies and transitive dependencies."
    
    # 1. Non-answer
    eval_zero = ai_service.generate_structured(
        system_prompt=sys_prompt,
        user_prompt="Learner's Submitted Answer: idk i don't remember",
        response_schema=OpenEndedEvaluation,
    )
    assert eval_zero.score == 0.0
    assert eval_zero.reasoning_quality == "poor"

    # 2. Substantive answer
    eval_good = ai_service.generate_structured(
        system_prompt=sys_prompt,
        user_prompt="Learner's Submitted Answer: Normalization decomposes relational tables to eliminate data anomalies and remove transitive dependencies.",
        response_schema=OpenEndedEvaluation,
    )
    assert eval_good.score >= 70.0
    assert eval_good.reasoning_quality in ("good", "fair")
    assert len(eval_good.what_you_understood) > 0

def test_concept_extraction_mock():
    """
    Verifies mock concept extraction produces substantive concept names dynamically
    rather than returning an unsupported-evidence reply.
    """
    sample_text = (
        "# Quantum Computing Principles\n"
        "Superposition allows qubits to exist in multiple states simultaneously.\n"
        "Quantum Entanglement links particles across distances.\n"
        "Quantum Gates perform unitary operations on qubit states."
    )
    reply = ai_service.generate_chat(
        system_prompt="You are an educational concept extractor. Analyze the provided study material and identify 3 to 6 major core concepts/topics covered. Respond with a plain comma-separated list of concept names only.",
        messages=[{"role": "user", "content": f"Extract 3-6 core concept names from this material:\n{sample_text}"}],
        feature="concept_extraction"
    )
    concepts = [c.strip() for c in reply.split(",") if c.strip()]
    assert len(concepts) >= 3
    # Check that it extracted real topics from the sample text
    extracted_lower = " ".join(concepts).lower()
    assert "quantum" in extracted_lower or "superposition" in extracted_lower or "entanglement" in extracted_lower
    # Ensure it's not returning canonical unsupported reply
    assert "couldn't find enough information" not in extracted_lower
