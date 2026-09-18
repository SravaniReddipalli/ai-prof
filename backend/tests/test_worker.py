import pytest
from app.models.models import BackgroundJob, Material
from app.workers.worker import WorkerService

def test_worker_claim_job(db_session, test_workspace, test_user):
    """Tests the worker's ability to claim a job."""
    proj_id = test_workspace["project"].id
    
    job = BackgroundJob(
        job_type="PROCESS_DOCUMENT",
        payload={
            "material_id": test_workspace["material"].id,
            "project_id": proj_id,
            "user_id": test_user.id,
        },
        status="QUEUED"
    )
    db_session.add(job)
    db_session.commit()
    
    # Claim it
    claimed = WorkerService.claim_next_job(db_session)
    assert claimed is not None
    assert claimed.id == job.id
    assert claimed.status == "PROCESSING"
    
    # Try claiming again - should be None
    second_claim = WorkerService.claim_next_job(db_session)
    assert second_claim is None
