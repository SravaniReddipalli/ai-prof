from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.models.models import (
    User, Space, Project, Material, Quiz, AIUsage, BackgroundJob, LearningEvent, QuizAttempt
)
from app.schemas.schemas import (
    AdminOverviewResponse, AdminUserInspectResponse, AIUsageItem, BackgroundJobItem, UserResponse
)
from app.api.deps import get_current_admin

router = APIRouter(prefix="/admin", tags=["Admin Dashboard"])

@router.get("/overview", response_model=AdminOverviewResponse)
def get_admin_overview(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    total_users = db.query(User).count()
    total_spaces = db.query(Space).count()
    total_projects = db.query(Project).count()
    total_materials = db.query(Material).count()
    total_quizzes = db.query(Quiz).count()

    total_ai_requests = db.query(AIUsage).count()
    failed_ai_requests = db.query(AIUsage).filter(AIUsage.success == False).count()
    all_usage = db.query(AIUsage).all()
    total_ai_cost = round(sum(u.estimated_cost_usd for u in all_usage), 4)

    active_jobs = db.query(BackgroundJob).filter(BackgroundJob.status.in_(["QUEUED", "PROCESSING"])).count()
    failed_jobs = db.query(BackgroundJob).filter(BackgroundJob.status == "FAILED").count()

    return AdminOverviewResponse(
        total_users=total_users,
        total_spaces=total_spaces,
        total_projects=total_projects,
        total_materials=total_materials,
        total_quizzes=total_quizzes,
        total_ai_requests=total_ai_requests,
        total_ai_cost_usd=total_ai_cost,
        failed_ai_requests=failed_ai_requests,
        active_background_jobs=active_jobs,
        failed_background_jobs=failed_jobs,
    )

@router.get("/users", response_model=List[UserResponse])
def list_all_users(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [UserResponse.model_validate(u) for u in users]

@router.get("/users/{user_id}", response_model=AdminUserInspectResponse)
def inspect_user(
    user_id: str,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    spaces_cnt = db.query(Space).filter(Space.user_id == user.id).count()
    projects_cnt = db.query(Project).filter(Project.user_id == user.id).count()
    quizzes_cnt = db.query(QuizAttempt).filter(QuizAttempt.user_id == user.id).count()
    materials_cnt = db.query(Material).filter(Material.user_id == user.id).count()

    ai_logs = db.query(AIUsage).filter(AIUsage.user_id == user.id).all()
    ai_cost = round(sum(u.estimated_cost_usd for u in ai_logs), 4)

    events = db.query(LearningEvent).filter(LearningEvent.user_id == user.id).order_by(LearningEvent.created_at.desc()).limit(15).all()
    recent_activity = [{"type": e.event_type, "timestamp": e.created_at.isoformat(), "payload": e.payload} for e in events]

    return AdminUserInspectResponse(
        user=UserResponse.model_validate(user),
        spaces_count=spaces_cnt,
        projects_count=projects_cnt,
        quizzes_count=quizzes_cnt,
        materials_count=materials_cnt,
        recent_activity=recent_activity,
        ai_requests_count=len(ai_logs),
        estimated_ai_cost_usd=ai_cost,
    )

@router.get("/ai-usage", response_model=List[AIUsageItem])
def get_ai_usage_logs(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
    limit: int = 50,
):
    logs = db.query(AIUsage).order_by(AIUsage.created_at.desc()).limit(limit).all()
    return [AIUsageItem.model_validate(l) for l in logs]

@router.get("/jobs", response_model=List[BackgroundJobItem])
def get_background_jobs(
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
    limit: int = 50,
):
    jobs = db.query(BackgroundJob).order_by(BackgroundJob.created_at.desc()).limit(limit).all()
    return [BackgroundJobItem.model_validate(j) for j in jobs]

@router.post("/jobs/{job_id}/retry", status_code=status.HTTP_200_OK)
def retry_job(
    job_id: str,
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    job = db.query(BackgroundJob).filter(BackgroundJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    job.status = "QUEUED"
    job.error_message = None
    job.attempts = 0
    db.commit()
    return {"status": "success", "message": f"Job {job_id} requeued for execution"}
