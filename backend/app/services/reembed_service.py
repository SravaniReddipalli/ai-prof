import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.models import DocumentChunk
from app.ai.openai_service import ai_service

logger = logging.getLogger(__name__)

def reembed_all_chunks(db: Session, project_id: Optional[str] = None, batch_size: int = 50) -> Dict[str, Any]:
    """
    Safely re-embeds existing document chunks using the current active embedding algorithm
    (e.g., deterministic lexical/term-feature retrieval embedding).
    
    Ensures existing materials and new chunks share the identical embedding representation space,
    preventing mixed or corrupted cosine distance retrieval in PostgreSQL/pgvector.
    """
    query = db.query(DocumentChunk)
    if project_id:
        query = query.filter(DocumentChunk.project_id == project_id)

    chunks = query.all()
    total = len(chunks)
    reembedded = 0

    logger.info(f"Starting re-embedding for {total} document chunks (project_id={project_id or 'ALL'})...")

    for idx, chunk in enumerate(chunks, 1):
        # Generate new deterministic lexical/term-feature embedding
        new_embedding = ai_service.get_embedding(chunk.content)
        chunk.embedding = new_embedding
        reembedded += 1

        if idx % batch_size == 0 or idx == total:
            db.commit()
            logger.info(f"Re-embedded {idx}/{total} document chunks...")

    logger.info(f"Successfully re-embedded all {reembedded} document chunks.")
    return {
        "total_chunks": total,
        "reembedded": reembedded,
        "project_id": project_id,
        "status": "completed",
    }
