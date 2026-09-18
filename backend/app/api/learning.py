from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.models.models import Project, User, Quiz, Recommendation, LearningEvent
from app.schemas.schemas import (
    QuizResponse, QuizSubmitRequest, QuizAttemptResponse,
    MasterySummaryResponse, RecommendationResponse
)
from app.api.deps import get_project_with_access, get_current_user
from app.services.learning_service import learning_service

router = APIRouter(tags=["Learning & Assessment"])

@router.post("/projects/{project_id}/quizzes/generate", response_model=QuizResponse, status_code=status.HTTP_201_CREATED)
def generate_quiz(
    project: Project = Depends(get_project_with_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    quiz = learning_service.generate_adaptive_quiz(project.id, current_user.id, db)
    return quiz

@router.get("/projects/{project_id}/quizzes", response_model=List[QuizResponse])
def list_quizzes(
    project: Project = Depends(get_project_with_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    quizzes = db.query(Quiz).filter(Quiz.project_id == project.id, Quiz.user_id == current_user.id).order_by(Quiz.created_at.desc()).all()
    results = []
    for q in quizzes:
        results.append(QuizResponse(
            id=q.id,
            project_id=q.project_id,
            title=q.title,
            difficulty=q.difficulty,
            questions=[],
            created_at=q.created_at,
        ))
    return results

@router.get("/quizzes/{quiz_id}", response_model=QuizResponse)
def get_quiz(
    quiz_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")
    if quiz.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    from app.schemas.schemas import QuizQuestionResponse
    q_responses = [
        QuizQuestionResponse(
            id=q.id,
            concept_id=q.concept_id,
            type=q.type,
            question=q.question,
            options=q.options,
            difficulty=q.difficulty,
        ) for q in quiz.questions
    ]
    return QuizResponse(
        id=quiz.id,
        project_id=quiz.project_id,
        title=quiz.title,
        difficulty=quiz.difficulty,
        questions=q_responses,
        created_at=quiz.created_at,
    )

@router.post("/quizzes/{quiz_id}/submit", response_model=QuizAttemptResponse)
def submit_quiz(
    quiz_id: str,
    req: QuizSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")
    if quiz.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    submissions = [{"question_id": a.question_id, "answer": a.answer} for a in req.answers]
    attempt = learning_service.evaluate_quiz_submission(quiz_id, current_user.id, submissions, db)
    return attempt

@router.get("/projects/{project_id}/mastery", response_model=MasterySummaryResponse)
def get_project_mastery(
    project: Project = Depends(get_project_with_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return learning_service.get_mastery_summary(project.id, current_user.id, db)

@router.get("/projects/{project_id}/recommendations", response_model=List[RecommendationResponse])
def get_recommendations(
    project: Project = Depends(get_project_with_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    recs = db.query(Recommendation).filter(
        Recommendation.project_id == project.id,
        Recommendation.user_id == current_user.id,
    ).order_by(Recommendation.created_at.desc()).all()

    # If none exist, auto-generate one
    if not recs:
        rec = learning_service.generate_recommendation(project.id, current_user.id, db)
        if rec:
            recs = [db.query(Recommendation).filter(Recommendation.id == rec.id).first()]

    return [RecommendationResponse.model_validate(r) for r in recs]

@router.post("/recommendations/{rec_id}/complete", status_code=status.HTTP_200_OK)
def complete_recommendation(
    rec_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rec = db.query(Recommendation).filter(Recommendation.id == rec_id).first()
    if not rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found")
    if rec.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    rec.is_completed = True
    db.commit()
    return {"status": "success", "message": "Recommendation marked as completed"}
