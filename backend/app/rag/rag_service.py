import logging
import re
from typing import List, Dict, Any, Tuple
from sqlalchemy import text
from app.core.config import settings
from app.models.models import DocumentChunk, Material, Conversation, Message, ConceptMastery, Concept, Project
from app.ai.openai_service import ai_service
from app.schemas.schemas import CitationItem, TutorChatResponse
from app.rag.text_matcher import extract_query_terms, count_term_matches, score_chunk_relevance

logger = logging.getLogger(__name__)

CANONICAL_UNSUPPORTED_REPLY = "I couldn't find enough information about that in the current Project materials to answer reliably."

class RAGService:
    @staticmethod
    def retrieve_project_chunks(
        project_id: str,
        query: str,
        db,
        top_k: int = 5,
        user_id: str = None,
    ) -> Tuple[List[Dict[str, Any]], List[float]]:
        """
        Retrieves the top-K most relevant chunks strictly scoped to the specified project_id.
        Computes cosine similarity and returns chunks with similarity scores.
        """
        query_vector = ai_service.get_embedding(query, db=db, user_id=user_id, project_id=project_id)
        vector_str = "[" + ",".join(str(x) for x in query_vector) + "]"

        # Strict project isolation query
        search_sql = text("""
            SELECT 
                dc.id,
                dc.material_id,
                dc.page_number,
                dc.chunk_index,
                dc.content,
                m.title AS material_title,
                (dc.embedding <=> CAST(:query_vector AS vector)) AS distance
            FROM document_chunks dc
            JOIN materials m ON dc.material_id = m.id
            WHERE dc.project_id = :project_id
              AND m.status = 'READY'
              AND dc.embedding IS NOT NULL
            ORDER BY distance ASC
            LIMIT :top_k;
        """)

        try:
            results = db.execute(search_sql, {
                "query_vector": vector_str,
                "project_id": project_id,
                "top_k": top_k,
            }).fetchall()
        except Exception as e:
            logger.warning(f"pgvector query failed (fallback to basic match): {e}")
            # Fallback for mock/test environments
            chunks_db = db.query(DocumentChunk, Material.title).\
                join(Material, DocumentChunk.material_id == Material.id).\
                filter(DocumentChunk.project_id == project_id, Material.status == "READY").\
                all()

            q_terms = extract_query_terms(query)
            scored_candidates = []
            for c, m_title in chunks_db:
                relevance_score = score_chunk_relevance(q_terms, c.content, m_title)
                distance = round(max(0.0, min(1.0, 1.0 - relevance_score)), 4)
                scored_candidates.append((c.id, c.material_id, c.page_number, c.chunk_index, c.content, m_title, distance))

            scored_candidates.sort(key=lambda x: x[6])
            results = scored_candidates[:top_k]

        retrieved = []
        scores = []
        for r in results:
            dist = float(r[6]) if r[6] is not None else 1.0
            similarity = max(0.0, 1.0 - dist)
            scores.append(round(similarity, 4))
            retrieved.append({
                "chunk_id": r[0],
                "material_id": r[1],
                "page_number": r[2],
                "chunk_index": r[3],
                "content": r[4],
                "material_title": r[5],
                "similarity": round(similarity, 4),
            })

        logger.info(f"Retrieved {len(retrieved)} chunks for project {project_id}. Similarities: {scores}")
        return retrieved, scores

    @staticmethod
    def build_learner_context(project_id: str, user_id: str, db) -> str:
        """Constructs a compact representation of learner goals, weak concepts, and recent performance."""
        project = db.query(Project).filter(Project.id == project_id).first()
        goal = project.learning_goal if project and project.learning_goal else "Master the project material."

        # Fetch weak concepts (score < 60)
        weak_masteries = db.query(ConceptMastery, Concept.name).\
            join(Concept, ConceptMastery.concept_id == Concept.id).\
            filter(ConceptMastery.project_id == project_id, ConceptMastery.user_id == user_id, ConceptMastery.score < 60.0).\
            order_by(ConceptMastery.score.asc()).limit(3).all()

        weak_names = [name for _, name in weak_masteries]
        weak_str = ", ".join(weak_names) if weak_names else "None identified yet"

        return f"Goal: {goal} | Focus Areas / Weak Concepts: {weak_str}"

    @staticmethod
    def _extract_query_terms(query: str) -> List[str]:
        """Extracts substantive concept terms from a query, filtering out stopwords and short words."""
        return extract_query_terms(query)

    @staticmethod
    def _filter_relevant_chunks(
        chunks: List[Dict[str, Any]],
        scores: List[float],
        query: str,
    ) -> Tuple[List[Dict[str, Any]], List[float]]:
        """
        Filters retrieved chunks to only those with substantive keyword or typo-tolerant relevance to the query.
        Retrieval must NOT be treated as evidence automatically — only chunks whose content
        has meaningful overlap with the query's concept terms are kept as evidence.
        """
        query_terms = RAGService._extract_query_terms(query)
        if not query_terms:
            return chunks, scores

        relevant_chunks = []
        relevant_scores = []

        for chunk, score in zip(chunks, scores):
            combined = f"{chunk['material_title']}\n{chunk['content']}"
            matches = count_term_matches(query_terms, combined)
            if matches > 0:
                relevant_chunks.append(chunk)
                relevant_scores.append(score)

        logger.info(
            f"Relevance filter: {len(chunks)} retrieved -> {len(relevant_chunks)} relevant "
            f"(query_terms={query_terms})"
        )
        return relevant_chunks, relevant_scores

    @staticmethod
    def answer_query(
        project_id: str,
        user_id: str,
        conversation_id: str,
        user_message: str,
        db,
    ) -> TutorChatResponse:
        """
        Executes grounded tutor interaction with project isolation, compact history, and holistic grounding check.
        """
        # 1. Retrieve project-scoped candidate chunks (broad retrieval)
        chunks, scores = RAGService.retrieve_project_chunks(
            project_id=project_id,
            query=user_message,
            db=db,
            top_k=8,
            user_id=user_id,
        )

        # 2. Check if project has NO ready materials at all or zero chunks
        if not chunks:
            # Check if any ready material exists
            ready_mats = db.query(Material).filter(Material.project_id == project_id, Material.status == "READY").count()
            if ready_mats == 0:
                reply = "No study materials are ready yet in this Project. Please upload a PDF to begin learning with the AI Tutor!"
                return TutorChatResponse(
                    message_id="",
                    reply=reply,
                    citations=[],
                    is_unsupported=True,
                    evidence_score=0.0,
                )

        # 3. Filter retrieved chunks to only those relevant to the query
        #    Retrieval is NOT evidence — only chunks with substantive keyword overlap qualify
        relevant_chunks, relevant_scores = RAGService._filter_relevant_chunks(
            chunks, scores, user_message,
        )

        # 4. Format compact context from RELEVANT chunks only
        context_blocks = []
        for i, c in enumerate(relevant_chunks):
            snippet = c['content'].replace('\n', ' ')
            context_blocks.append(
                f"[Source {i+1}: {c['material_title']} | Page: {c['page_number']}]\n{snippet}"
            )
        combined_context = "\n\n".join(context_blocks) if context_blocks else "NO EVIDENCE AVAILABLE."

        learner_context = RAGService.build_learner_context(project_id, user_id, db)

        system_prompt = (
            "You are AI.Prof, an expert pedagogical AI Study Tutor. "
            "Your purpose is to help the student learn deeply while remaining strictly grounded in their Project study materials.\n\n"
            "--- PROJECT MATERIALS EVIDENCE ---\n"
            f"{combined_context}\n"
            "----------------------------------\n\n"
            f"LEARNER PROFILE: {learner_context}\n\n"
            "CRITICAL OPERATIONAL RULES:\n"
            "1. Base your answer ONLY on the provided Project Materials Evidence.\n"
            f"2. If the provided evidence does not contain sufficient factual information to answer the question reliably, you MUST respond EXACTLY with:\n"
            f"\"{CANONICAL_UNSUPPORTED_REPLY}\"\n"
            "   Do not guess, hallucinate, extrapolate, or draw from outside world knowledge.\n"
            "3. If evidence IS sufficient, directly answer the user's question with a substantive explanation synthesizing the retrieved evidence. Do NOT provide generic placeholders or tell the user to read their notes without explaining the material yourself. Explain the concepts and mechanics clearly using the evidence.\n"
            "4. Conclude your answer with an explicit citation in the exact format:\n"
            "   Source: <Material Name> — Page <Number>\n"
        )

        # 5. Compact conversation history: sliding window of last 4 messages
        recent_messages = db.query(Message).\
            filter(Message.conversation_id == conversation_id).\
            order_by(Message.created_at.desc()).\
            limit(4).all()
        recent_messages.reverse()

        dialogue_history = []
        for m in recent_messages:
            role = "user" if m.sender == "user" else "assistant"
            dialogue_history.append({"role": role, "content": m.content})

        dialogue_history.append({"role": "user", "content": user_message})

        # 6. Generate Tutor response
        top_score = relevant_scores[0] if relevant_scores else 0.0
        
        path_type = "MOCK_AI" if not ai_service.client else "REAL_OPENAI"
        logger.info(f"[TUTOR_PATH] Executing AI generation via: {path_type}")
        
        ai_reply = ai_service.generate_chat(
            system_prompt=system_prompt,
            messages=dialogue_history,
            db=db,
            feature="tutor",
            user_id=user_id,
            project_id=project_id,
            retrieval_scores=relevant_scores,
        )

        # 7. Evaluate grounding / unsupportedness
        is_unsupported = False
        citations: List[CitationItem] = []

        is_fully_unsupported = (
            ai_reply.strip() == CANONICAL_UNSUPPORTED_REPLY
            or (CANONICAL_UNSUPPORTED_REPLY.lower() in ai_reply.lower() and "Based on your Project materials:" not in ai_reply)
        )

        if is_fully_unsupported:
            is_unsupported = True
            citations = []
            ai_reply = CANONICAL_UNSUPPORTED_REPLY
        else:
            ai_reply = ai_reply.replace("svgSource:", "Source:")
            # Build structured citations only from chunks actually cited in the reply
            reply_lower = ai_reply.lower()
            for c in relevant_chunks:
                clean_src = c["material_title"].replace("svgSource:", "").replace("Source:", "").strip()
                # Check if this chunk's citation (Source: X — Page Y) appears in the reply text
                cite_marker = f"page {c['page_number']}"
                src_marker = clean_src.lower()
                if cite_marker in reply_lower and src_marker in reply_lower:
                    citations.append(CitationItem(
                        source=clean_src,
                        page=c["page_number"],
                        snippet=c["content"][:160] + "...",
                    ))

        # 8. Persist messages to DB
        user_msg_record = Message(
            conversation_id=conversation_id,
            sender="user",
            content=user_message,
            is_unsupported=False,
        )
        db.add(user_msg_record)

        assistant_msg_record = Message(
            conversation_id=conversation_id,
            sender="assistant",
            content=ai_reply,
            citations=[c.model_dump() for c in citations] if citations else None,
            is_unsupported=is_unsupported,
        )
        db.add(assistant_msg_record)
        db.commit()
        db.refresh(assistant_msg_record)

        return TutorChatResponse(
            message_id=assistant_msg_record.id,
            reply=ai_reply,
            citations=citations,
            is_unsupported=is_unsupported,
            evidence_score=top_score,
        )


rag_service = RAGService()
