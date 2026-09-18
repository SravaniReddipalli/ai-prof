from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.models.models import Project, User, Conversation, Message, LearningEvent
from app.schemas.schemas import TutorChatRequest, TutorChatResponse, MessageHistoryItem, CitationItem
from app.api.deps import get_project_with_access, get_current_user
from app.rag.rag_service import rag_service

router = APIRouter(prefix="/projects", tags=["AI Tutor"])

def get_or_create_conversation(project_id: str, user_id: str, db: Session) -> Conversation:
    conv = db.query(Conversation).filter(
        Conversation.project_id == project_id,
        Conversation.user_id == user_id,
    ).first()
    if not conv:
        conv = Conversation(project_id=project_id, user_id=user_id, title="AI Tutor Session")
        db.add(conv)
        db.commit()
        db.refresh(conv)
    return conv

@router.post("/{project_id}/tutor/chat", response_model=TutorChatResponse)
def tutor_chat(
    project_id: str,
    req: TutorChatRequest,
    project: Project = Depends(get_project_with_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = get_or_create_conversation(project.id, current_user.id, db)
    
    response = rag_service.answer_query(
        project_id=project.id,
        user_id=current_user.id,
        conversation_id=conv.id,
        user_message=req.message,
        db=db,
    )

    event = LearningEvent(
        user_id=current_user.id,
        project_id=project.id,
        event_type="TUTOR_INTERACTION",
        payload={
            "query": req.message[:100],
            "is_unsupported": response.is_unsupported,
            "citations_count": len(response.citations),
        },
    )
    db.add(event)
    db.commit()

    return response

@router.get("/{project_id}/tutor/history", response_model=List[MessageHistoryItem])
def get_tutor_history(
    project: Project = Depends(get_project_with_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = get_or_create_conversation(project.id, current_user.id, db)
    messages = db.query(Message).filter(Message.conversation_id == conv.id).order_by(Message.created_at.asc()).all()
    
    results = []
    for m in messages:
        citations = [CitationItem(**c) for c in m.citations] if m.citations else None
        results.append(MessageHistoryItem(
            id=m.id,
            sender=m.sender,
            content=m.content,
            citations=citations,
            is_unsupported=m.is_unsupported,
            created_at=m.created_at,
        ))
    return results

@router.post("/{project_id}/tutor/clear", status_code=status.HTTP_204_NO_CONTENT)
def clear_tutor_history(
    project: Project = Depends(get_project_with_access),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conv = get_or_create_conversation(project.id, current_user.id, db)
    db.query(Message).filter(Message.conversation_id == conv.id).delete()
    db.commit()
    return None
