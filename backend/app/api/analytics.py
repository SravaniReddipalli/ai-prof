from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.models import (
    Project, User, Space, Material, DocumentChunk, 
    QuizAttempt, Conversation, Message, LearningEvent, ConceptMastery, Concept
)
from app.schemas.schemas import ProjectAnalyticsResponse, GlobalAnalyticsResponse
from app.api.deps import get_project_with_access, get_current_user

router = APIRouter(tags=["Analytics"])

@router.get("/projects/{project_id}/analytics", response_model=ProjectAnalyticsResponse)
def get_project_analytics(
    project: Project = Depends(get_project_with_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    total_materials = db.query(Material).filter(Material.project_id == project.id).count()
    total_chunks = db.query(DocumentChunk).filter(DocumentChunk.project_id == project.id).count()
    
    attempts = db.query(QuizAttempt).filter(
        QuizAttempt.project_id == project.id,
        QuizAttempt.user_id == current_user.id,
    ).all()
    quizzes_taken = len(attempts)
    avg_score = round(sum(a.score for a in attempts) / max(quizzes_taken, 1), 1) if quizzes_taken else 0.0

    conv = db.query(Conversation).filter(
        Conversation.project_id == project.id,
        Conversation.user_id == current_user.id,
    ).first()
    tutor_msgs_count = len(conv.messages) if conv else 0

    # Concept breakdown
    masteries = db.query(ConceptMastery, Concept.name).\
        join(Concept, ConceptMastery.concept_id == Concept.id).\
        filter(ConceptMastery.project_id == project.id, ConceptMastery.user_id == current_user.id).all()

    concept_scores = [{"name": name, "score": cm.score, "status": cm.status} for cm, name in masteries]
    overall_mastery = round(sum(c["score"] for c in concept_scores) / max(len(concept_scores), 1), 1) if concept_scores else 0.0

    # Recent events
    events = db.query(LearningEvent).filter(
        LearningEvent.project_id == project.id,
        LearningEvent.user_id == current_user.id,
    ).order_by(LearningEvent.created_at.desc()).limit(10).all()

    recent_events = [{"type": e.event_type, "timestamp": e.created_at.isoformat(), "payload": e.payload} for e in events]

    return ProjectAnalyticsResponse(
        project_id=project.id,
        learning_goal=project.learning_goal,
        total_materials=total_materials,
        total_chunks=total_chunks,
        overall_mastery=overall_mastery,
        quizzes_taken=quizzes_taken,
        average_quiz_score=avg_score,
        tutor_messages_count=tutor_msgs_count,
        concept_scores=concept_scores,
        recent_events=recent_events,
    )

@router.get("/analytics/global", response_model=GlobalAnalyticsResponse)
def get_global_analytics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    total_spaces = db.query(Space).filter(Space.user_id == current_user.id).count()
    total_projects = db.query(Project).filter(Project.user_id == current_user.id).count()
    total_materials = db.query(Material).filter(Material.user_id == current_user.id).count()
    
    attempts = db.query(QuizAttempt).filter(QuizAttempt.user_id == current_user.id).all()
    quizzes_completed = len(attempts)
    avg_score = round(sum(a.score for a in attempts) / max(quizzes_completed, 1), 1) if quizzes_completed else 0.0

    recent_events = db.query(LearningEvent).filter(
        LearningEvent.user_id == current_user.id,
    ).order_by(LearningEvent.created_at.desc()).limit(10).all()

    activity_log = [{"type": e.event_type, "timestamp": e.created_at.isoformat(), "payload": e.payload} for e in recent_events]

    return GlobalAnalyticsResponse(
        total_spaces=total_spaces,
        total_projects=total_projects,
        total_materials=total_materials,
        total_quizzes_completed=quizzes_completed,
        average_platform_score=avg_score,
        active_streak_days=1 if quizzes_completed or total_projects else 0,
        recent_activity=activity_log,
    )
