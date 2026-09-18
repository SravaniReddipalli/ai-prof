from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.models.models import Space, Project, User, LearningEvent
from app.schemas.schemas import SpaceCreate, SpaceUpdate, SpaceResponse, ProjectCreate, ProjectResponse
from app.api.deps import get_current_user

router = APIRouter(prefix="/spaces", tags=["Spaces"])

@router.get("", response_model=List[SpaceResponse])
def list_spaces(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    spaces = db.query(Space).filter(Space.user_id == current_user.id).order_by(Space.created_at.desc()).all()
    results = []
    for s in spaces:
        proj_count = db.query(Project).filter(Project.space_id == s.id).count()
        s_dict = SpaceResponse.model_validate(s)
        s_dict.project_count = proj_count
        results.append(s_dict)
    return results

@router.post("", response_model=SpaceResponse, status_code=status.HTTP_201_CREATED)
def create_space(req: SpaceCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    new_space = Space(
        user_id=current_user.id,
        name=req.name,
        description=req.description,
        icon=req.icon or "folder",
        color=req.color or "indigo",
    )
    db.add(new_space)
    db.commit()
    db.refresh(new_space)

    event = LearningEvent(
        user_id=current_user.id,
        event_type="SPACE_CREATED",
        payload={"space_id": new_space.id, "name": new_space.name},
    )
    db.add(event)
    db.commit()

    resp = SpaceResponse.model_validate(new_space)
    resp.project_count = 0
    return resp

@router.get("/{space_id}", response_model=SpaceResponse)
def get_space(space_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    space = db.query(Space).filter(Space.id == space_id).first()
    if not space:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Space not found")
    if space.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    proj_count = db.query(Project).filter(Project.space_id == space.id).count()
    resp = SpaceResponse.model_validate(space)
    resp.project_count = proj_count
    return resp

@router.delete("/{space_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_space(space_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    space = db.query(Space).filter(Space.id == space_id).first()
    if not space:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Space not found")
    if space.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    db.delete(space)
    db.commit()
    return None

@router.get("/{space_id}/projects", response_model=List[ProjectResponse])
def list_space_projects(space_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    space = db.query(Space).filter(Space.id == space_id).first()
    if not space:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Space not found")
    if space.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    projects = db.query(Project).filter(Project.space_id == space_id).order_by(Project.created_at.desc()).all()
    results = []
    for p in projects:
        resp = ProjectResponse.model_validate(p)
        resp.material_count = len(p.materials)
        resp.concept_count = len(p.concepts)
        results.append(resp)
    return results

@router.post("/{space_id}/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(space_id: str, req: ProjectCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    space = db.query(Space).filter(Space.id == space_id).first()
    if not space:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Space not found")
    if space.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    new_project = Project(
        space_id=space_id,
        user_id=current_user.id,
        name=req.name,
        description=req.description,
        learning_goal=req.learning_goal,
    )
    db.add(new_project)
    db.commit()
    db.refresh(new_project)

    event = LearningEvent(
        user_id=current_user.id,
        project_id=new_project.id,
        event_type="PROJECT_CREATED",
        payload={"project_id": new_project.id, "name": new_project.name, "goal": new_project.learning_goal},
    )
    db.add(event)
    db.commit()

    resp = ProjectResponse.model_validate(new_project)
    resp.material_count = 0
    resp.concept_count = 0
    return resp
