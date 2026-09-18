import time
import logging
from sqlalchemy import text
from app.core.database import SessionLocal
from app.models.models import BackgroundJob, Material, DocumentChunk, LearningEvent
from app.storage.service import get_storage_service
from app.services.document_service import document_service
from app.ai.openai_service import ai_service

logger = logging.getLogger(__name__)

class WorkerService:
    @staticmethod
    def claim_next_job(db) -> BackgroundJob:
        """
        Safely claims the oldest pending QUEUED job using PostgreSQL row-level locking (SKIP LOCKED).
        This guarantees zero concurrency conflicts between multiple worker instances.
        """
        try:
            # Query for next available queued job with row locking
            claim_sql = text("""
                SELECT id FROM background_jobs 
                WHERE status = 'QUEUED' 
                ORDER BY created_at ASC 
                LIMIT 1 
                FOR UPDATE SKIP LOCKED;
            """)
            result = db.execute(claim_sql).first()
            if not result:
                return None

            job_id = result[0]
            job = db.query(BackgroundJob).filter(BackgroundJob.id == job_id).first()
            if job:
                job.status = "PROCESSING"
                job.attempts += 1
                db.commit()
                db.refresh(job)
                return job
        except Exception as e:
            db.rollback()
            # If dialect does not support FOR UPDATE SKIP LOCKED (e.g. SQLite in test harness), fallback safely
            job = db.query(BackgroundJob).filter(BackgroundJob.status == "QUEUED").order_by(BackgroundJob.created_at.asc()).first()
            if job:
                job.status = "PROCESSING"
                job.attempts += 1
                db.commit()
                db.refresh(job)
                return job
        return None

    @staticmethod
    def process_job(job: BackgroundJob, db):
        """Dispatches job execution based on job_type."""
        logger.info(f"Processing job {job.id} of type {job.job_type} (attempt {job.attempts}/{job.max_attempts})")
        if job.job_type == "PROCESS_DOCUMENT":
            WorkerService._process_document(job, db)
        else:
            logger.warning(f"Unknown job type: {job.job_type}")
            job.status = "READY"
            db.commit()

    @staticmethod
    def _process_document(job: BackgroundJob, db):
        payload = job.payload or {}
        material_id = payload.get("material_id")
        project_id = payload.get("project_id")
        user_id = payload.get("user_id")

        material = db.query(Material).filter(Material.id == material_id).first()
        if not material:
            job.status = "FAILED"
            job.error_message = f"Material {material_id} not found"
            db.commit()
            return

        try:
            material.status = "PROCESSING"
            db.commit()

            # 1. Download file bytes via persistent StorageService
            storage = get_storage_service()
            file_bytes = storage.download_file(material.storage_key)

            # 2. Extract PDF pages with PyMuPDF
            pages = document_service.extract_pdf_pages(file_bytes)
            material.page_count = len(pages)

            # 3. Chunk pages preserving page numbers
            raw_chunks = document_service.chunk_pages(pages, chunk_size=800, overlap=100)

            # Delete any previous chunks for idempotency if retrying
            db.query(DocumentChunk).filter(DocumentChunk.material_id == material.id).delete()
            db.commit()

            # 4. Generate embeddings and store chunks
            for chunk_data in raw_chunks:
                embedding_vector = ai_service.get_embedding(
                    chunk_data["content"],
                    db=db,
                    user_id=user_id,
                    project_id=project_id,
                )
                chunk_record = DocumentChunk(
                    material_id=material.id,
                    project_id=project_id,
                    page_number=chunk_data["page_number"],
                    chunk_index=chunk_data["chunk_index"],
                    content=chunk_data["content"],
                    token_count=chunk_data["token_count"],
                    embedding=embedding_vector,
                )
                db.add(chunk_record)

            db.commit()

            # 5. CRITICAL: Material is marked READY immediately once text, chunks, and embeddings succeed
            material.status = "READY"
            material.error_message = None
            job.status = "READY"
            job.error_message = None

            # Log learning event
            event = LearningEvent(
                user_id=user_id,
                project_id=project_id,
                event_type="MATERIAL_READY",
                payload={"material_id": material.id, "title": material.title, "pages": len(pages), "chunks": len(raw_chunks)},
            )
            db.add(event)
            db.commit()
            logger.info(f"Material {material.id} ('{material.title}') successfully processed and is READY.")

            # 6. Non-blocking concept extraction (failures do not block material readiness)
            document_service.extract_concepts_safely(pages, project_id, db, user_id=user_id)

        except Exception as e:
            logger.error(f"Error processing material {material.id}: {e}", exc_info=True)
            db.rollback()
            if job.attempts >= job.max_attempts:
                job.status = "FAILED"
                job.error_message = str(e)
                material.status = "FAILED"
                material.error_message = str(e)
            else:
                job.status = "QUEUED"  # Requeue for retry
                material.status = "QUEUED"
            db.commit()


def run_worker_once():
    """Runs a single pass of job claiming and processing."""
    db = SessionLocal()
    try:
        job = WorkerService.claim_next_job(db)
        if job:
            WorkerService.process_job(job, db)
            return True
        return False
    finally:
        db.close()

def run_worker_daemon(poll_interval: float = 2.0):
    """Continuous worker daemon loop for background task processing."""
    logger.info("Starting background worker daemon...")
    while True:
        try:
            processed = run_worker_once()
            if not processed:
                time.sleep(poll_interval)
        except Exception as e:
            logger.error(f"Unexpected worker error in daemon loop: {e}")
            time.sleep(poll_interval)


if __name__ == "__main__":
    run_worker_daemon()
