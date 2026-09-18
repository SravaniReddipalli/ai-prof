import pytest
from app.models.models import ConceptMastery, Concept, MasteryHistory, Quiz, QuizQuestion, QuizAttempt
from app.services.learning_service import learning_service

def test_mastery_initialization(db_session, test_workspace, test_user):
    """Verifies default masteries are created correctly."""
    proj_id = test_workspace["project"].id
    
    # Initialize masteries
    masteries = learning_service.get_or_create_masteries(proj_id, test_user.id, db_session)
    assert len(masteries) == 1
    assert masteries[0].score == 50.0
    assert masteries[0].status == "attention"

def test_adaptive_quiz_generation(db_session, test_workspace, test_user):
    """Verifies that an adaptive quiz can be generated deterministically."""
    proj_id = test_workspace["project"].id
    
    quiz_res = learning_service.generate_adaptive_quiz(proj_id, test_user.id, db_session)
    assert quiz_res.title is not None
    assert len(quiz_res.questions) == 4
    
    # Verify MCQ and Open Ended mix
    mcq_count = sum(1 for q in quiz_res.questions if q.type == "mcq")
    open_count = sum(1 for q in quiz_res.questions if q.type == "open_ended")
    assert mcq_count == 3
    assert open_count == 1

def test_quiz_evaluation_and_mastery_update(db_session, test_workspace, test_user):
    """Verifies quiz submission updates mastery scores."""
    proj_id = test_workspace["project"].id
    
    # Generate quiz
    quiz_res = learning_service.generate_adaptive_quiz(proj_id, test_user.id, db_session)
    
    # Simulate perfect answers for MCQs
    submissions = []
    for q in quiz_res.questions:
        if q.type == "mcq":
            submissions.append({"question_id": q.id, "answer": q.options[0]})  # mock answer
        else:
            submissions.append({"question_id": q.id, "answer": "This is a detailed open-ended response."})
            
    attempt = learning_service.evaluate_quiz_submission(quiz_res.id, test_user.id, submissions, db_session)
    
    assert attempt.score > 0
    assert len(attempt.question_results) == 4
    
    # Check if mastery was updated
    masteries = learning_service.get_or_create_masteries(proj_id, test_user.id, db_session)
    # The initial was 50.0. A score > 0 will change it.
    assert masteries[0].assessment_count == 1

def test_open_ended_grading_non_answer(db_session, test_workspace, test_user):
    """Verifies that non-answers like 'i dont know', empty string, or 'idk' receive 0% and do not claim concepts were understood."""
    proj_id = test_workspace["project"].id
    quiz_res = learning_service.generate_adaptive_quiz(proj_id, test_user.id, db_session)

    non_answers = ["i dont know", "I don't know", "", "idk", "no idea"]
    open_q = next(q for q in quiz_res.questions if q.type == "open_ended")

    for non_ans in non_answers:
        submissions = [{"question_id": open_q.id, "answer": non_ans}]
        for q in quiz_res.questions:
            if q.type == "mcq":
                submissions.append({"question_id": q.id, "answer": q.options[0]})

        attempt = learning_service.evaluate_quiz_submission(quiz_res.id, test_user.id, submissions, db_session)
        open_result = next(r for r in attempt.question_results if r.question_id == open_q.id)

        assert open_result.evaluation is not None
        assert open_result.evaluation.score == 0.0
        assert open_result.evaluation.what_you_understood == []
        assert open_result.evaluation.concepts_covered == []
        assert open_result.evaluation.reasoning_quality == "poor"
        assert open_result.evaluation.confidence >= 0.9
        assert open_result.is_correct is False

def test_mastery_mistake_count_consistency(db_session, test_workspace, test_user):
    """
    Verifies that when an assessment completes with 1 mistake, the ConceptMastery
    mistake_count increments by 1 even when the overall score is >= 60.0 (e.g., 75.0%),
    staying consistent with the ASSESSMENT_COMPLETED analytics event.
    """
    proj_id = test_workspace["project"].id
    quiz_res = learning_service.generate_adaptive_quiz(proj_id, test_user.id, db_session)

    # Initial mastery state: mistake_count = 0
    init_masteries = learning_service.get_or_create_masteries(proj_id, test_user.id, db_session)
    assert init_masteries[0].mistake_count == 0

    # Submit 3 correct MCQs (100% each) and 1 non-answer open-ended (0%) -> overall score = 75.0%
    submissions = []
    for q in quiz_res.questions:
        if q.type == "mcq":
            submissions.append({"question_id": q.id, "answer": q.options[0]})  # correct option
        else:
            submissions.append({"question_id": q.id, "answer": "i dont know"})

    attempt = learning_service.evaluate_quiz_submission(quiz_res.id, test_user.id, submissions, db_session)

    # Check overall score is 75.0% (which is >= 60.0%)
    assert attempt.score == 75.0

    # Check analytics event recorded in DB
    from app.models.models import LearningEvent
    event = db_session.query(LearningEvent).filter(
        LearningEvent.project_id == proj_id,
        LearningEvent.event_type == "ASSESSMENT_COMPLETED",
    ).order_by(LearningEvent.created_at.desc()).first()

    assert event is not None
    assert event.payload["score"] == 75.0
    assert event.payload["mistakes"] == 1

    # Check ConceptMastery row has mistake_count == 1 (not 0!)
    updated_masteries = learning_service.get_or_create_masteries(proj_id, test_user.id, db_session)
    assert updated_masteries[0].mistake_count == 1

    # Check Mastery Summary API response reflects mistake_count == 1
    summary = learning_service.get_mastery_summary(proj_id, test_user.id, db_session)
    matching_item = next(c for c in summary.concepts if c.concept_id == updated_masteries[0].concept_id)
    assert matching_item.mistake_count == 1
