import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.models.models import Material, BackgroundJob, LearningEvent, Project, User
from app.schemas.schemas import MaterialResponse, MaterialStatusResponse
from app.api.deps import get_project_with_access, get_current_user
from app.storage.service import get_storage_service
from app.workers.worker import run_worker_once

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Materials"])

@router.post("/projects/{project_id}/materials/upload", response_model=MaterialResponse, status_code=status.HTTP_201_CREATED)
async def upload_material(
    project_id: str,
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    project: Project = Depends(get_project_with_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Currently only PDF documents (.pdf) are supported",
        )

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")

    file_ext = ".pdf"
    unique_key = f"projects/{project_id}/materials/{uuid.uuid4().hex}{file_ext}"

    # Upload to persistent storage abstraction (Local or S3/Supabase)
    storage = get_storage_service()
    storage_key = storage.upload_file(unique_key, file_bytes, content_type="application/pdf")

    new_material = Material(
        project_id=project_id,
        user_id=current_user.id,
        title=file.filename.rsplit(".", 1)[0],
        filename=file.filename,
        storage_key=storage_key,
        file_size_bytes=len(file_bytes),
        page_count=0,
        status="QUEUED",
    )
    db.add(new_material)
    db.commit()
    db.refresh(new_material)

    # Create persistent background job in database
    job = BackgroundJob(
        job_type="PROCESS_DOCUMENT",
        payload={
            "material_id": new_material.id,
            "project_id": project_id,
            "user_id": current_user.id,
        },
        status="QUEUED",
    )
    db.add(job)

    # Log event
    event = LearningEvent(
        user_id=current_user.id,
        project_id=project_id,
        event_type="MATERIAL_UPLOADED",
        payload={"material_id": new_material.id, "filename": file.filename},
    )
    db.add(event)
    db.commit()
    db.refresh(job)

    # Trigger async execution via FastAPI background tasks (uses its own DB session)
    if background_tasks:
        background_tasks.add_task(run_worker_once)

    return MaterialResponse.model_validate(new_material)

@router.get("/projects/{project_id}/materials", response_model=List[MaterialResponse])
def list_project_materials(
    project: Project = Depends(get_project_with_access),
    db: Session = Depends(get_db),
):
    materials = db.query(Material).filter(Material.project_id == project.id).order_by(Material.created_at.desc()).all()
    return [MaterialResponse.model_validate(m) for m in materials]

@router.get("/materials/{material_id}/status", response_model=MaterialStatusResponse)
def get_material_status(
    material_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    mat = db.query(Material).filter(Material.id == material_id).first()
    if not mat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")
    if mat.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return MaterialStatusResponse(
        id=mat.id,
        status=mat.status,
        error_message=mat.error_message,
        page_count=mat.page_count,
    )

@router.delete("/materials/{material_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_material(
    material_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    mat = db.query(Material).filter(Material.id == material_id).first()
    if not mat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material not found")
    if mat.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # Delete storage file
    try:
        storage = get_storage_service()
        storage.delete_file(mat.storage_key)
    except Exception as e:
        logger.warning(f"Failed to delete storage file for material {mat.id}: {e}")

    db.delete(mat)
    db.commit()
    return None
