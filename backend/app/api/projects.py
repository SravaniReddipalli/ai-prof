from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.models import Project, LearningEvent
from app.schemas.schemas import ProjectResponse, ProjectUpdate
from app.api.deps import get_project_with_access, get_current_user

router = APIRouter(prefix="/projects", tags=["Projects"])

@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project: Project = Depends(get_project_with_access)):
    resp = ProjectResponse.model_validate(project)
    resp.material_count = len(project.materials)
    resp.concept_count = len(project.concepts)
    return resp

@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(
    req: ProjectUpdate,
    project: Project = Depends(get_project_with_access),
    db: Session = Depends(get_db),
):
    if req.name is not None:
        project.name = req.name
    if req.description is not None:
        project.description = req.description
    if req.learning_goal is not None:
        project.learning_goal = req.learning_goal

    db.commit()
    db.refresh(project)

    resp = ProjectResponse.model_validate(project)
    resp.material_count = len(project.materials)
    resp.concept_count = len(project.concepts)
    return resp

@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project: Project = Depends(get_project_with_access),
    db: Session = Depends(get_db),
):
    db.delete(project)
    db.commit()
    return None
