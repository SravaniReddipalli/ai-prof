import pymupdf
import re
import logging
from typing import List, Dict, Any, Tuple
from app.models.models import Concept
from app.ai.openai_service import ai_service

logger = logging.getLogger(__name__)

class DocumentService:
    @staticmethod
    def extract_pdf_pages(pdf_bytes: bytes) -> List[Dict[str, Any]]:
        """Extracts text per page from PDF bytes using PyMuPDF."""
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        pages = []
        try:
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text").strip()
                pages.append({
                    "page_number": page_num + 1,
                    "text": text if text else f"[Page {page_num + 1} contains images or non-selectable graphics]",
                })
        finally:
            doc.close()
        return pages

    @staticmethod
    def chunk_pages(pages: List[Dict[str, Any]], chunk_size: int = 800, overlap: int = 100) -> List[Dict[str, Any]]:
        """Splits page text into overlapping chunks, strictly preserving page numbers."""
        chunks = []
        global_chunk_idx = 0

        for page in pages:
            page_num = page["page_number"]
            text = page["text"]
            if not text:
                continue

            # Split into paragraphs or sentences if possible
            start = 0
            text_len = len(text)
            while start < text_len:
                end = min(start + chunk_size, text_len)
                # Try to break at a newline or space if not at the very end
                if end < text_len:
                    break_pt = text.rfind(" ", start, end)
                    if break_pt > start + (chunk_size // 2):
                        end = break_pt

                chunk_content = text[start:end].strip()
                if chunk_content:
                    chunks.append({
                        "page_number": page_num,
                        "chunk_index": global_chunk_idx,
                        "content": chunk_content,
                        "token_count": max(1, len(chunk_content) // 4),
                    })
                    global_chunk_idx += 1

                if end >= text_len:
                    break
                start = end - overlap if (end - overlap) > start else end

        return chunks

    @staticmethod
    def extract_concepts_safely(pages: List[Dict[str, Any]], project_id: str, db, user_id: str = None) -> List[str]:
        """
        Non-blocking concept extractor.
        Analyzes the first few pages or key terms to extract core concepts.
        Catches all exceptions so concept extraction never fails the document pipeline.
        """
        try:
            sample_text = "\n".join(p["text"][:600] for p in pages[:4])
            if not sample_text.strip():
                return []

            system_prompt = (
                "You are an educational concept extractor. Analyze the provided study material "
                "and identify 3 to 6 major core concepts/topics covered. "
                "Respond with a plain comma-separated list of concept names only (e.g. Normalization, Transactions, B-Tree Indexing)."
            )
            raw_response = ai_service.generate_chat(
                system_prompt=system_prompt,
                messages=[{"role": "user", "content": f"Extract 3-6 core concept names from this material:\n{sample_text}"}],
                db=db,
                feature="concept_extraction",
                user_id=user_id,
                project_id=project_id,
            )

            concept_names = [c.strip() for c in raw_response.split(",") if c.strip() and len(c.strip()) < 60]
            if not concept_names:
                concept_names = ["Core Foundations", "Key Principles"]

            created = []
            for name in concept_names:
                # Check if concept already exists for this project
                existing = db.query(Concept).filter(Concept.project_id == project_id, Concept.name == name).first()
                if not existing:
                    new_concept = Concept(project_id=project_id, name=name, description=f"Core concept: {name}")
                    db.add(new_concept)
                    created.append(name)
            db.commit()
            logger.info(f"Safely extracted and registered {len(created)} concepts for project {project_id}")
            return created
        except Exception as e:
            logger.warning(f"Non-blocking concept extraction encountered an error (ignored): {e}")
            db.rollback()
            return []


document_service = DocumentService()
