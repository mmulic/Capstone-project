"""
Chat Router (BE-016, BE-017)
==============================
POST /api/chat — Chatbot endpoint with RAG context retrieval and session history
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.models import ChatSession, ChatMessage
from app.services.rag_service import rag_service
from app.services.llm_service import llm_service
from app.schemas.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/api", tags=["Chatbot"])

MAX_HISTORY_TURNS = 10


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Natural language chatbot for querying disaster assessment data.

    Pipeline:
    1. Load or create chat session
    2. Retrieve relevant context via RAG (PostGIS spatial + keyword search)
    3. Send message + context + history to LLM service (Gemini)
    4. Store conversation turn and return response

    Example queries:
    - "What is the damage at 123 Main Street?"
    - "How many properties were destroyed?"
    - "Summarize damage in downtown area"
    - "Show me the worst-hit properties"
    """
    # 1. Get or create session
    session_id = request.session_id
    if session_id:
        session = await db.get(ChatSession, session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    else:
        session = ChatSession()
        db.add(session)
        await db.flush()

    # 2. Load conversation history
    history_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at)
    )
    history_messages = history_result.scalars().all()

    # Format history for LLM (keep last N turns)
    history = [
        {"role": msg.role, "content": msg.content}
        for msg in history_messages[-(MAX_HISTORY_TURNS * 2):]
    ]

    # 3. Retrieve relevant context via RAG
    context_data = await rag_service.retrieve_context(
        query=request.message, db=db
    )
    formatted_context = context_data.get("formatted_context", "")

    # 4. Call LLM service (ML person's Gemini implementation or mock)
    response_text = await llm_service.generate_response(
        message=request.message,
        context=formatted_context,
        history=history,
    )

    # 5. Store conversation turn
    user_msg = ChatMessage(
        session_id=session.id,
        role="user",
        content=request.message,
    )
    assistant_msg = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=response_text,
        context_used=formatted_context[:2000] if formatted_context else None,
    )
    db.add(user_msg)
    db.add(assistant_msg)
    await db.flush()

    return ChatResponse(
        response=response_text,
        session_id=session.id,
        context_used={
            "strategy": context_data.get("strategy"),
            "num_results": len(context_data.get("results", [])),
            "summary": context_data.get("summary"),
        },
    )


@router.get("/chat/{session_id}/history")
async def get_chat_history(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve conversation history for a chat session."""
    session = await db.get(ChatSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    messages_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    messages = messages_result.scalars().all()

    return {
        "session_id": str(session_id),
        "message_count": len(messages),
        "messages": [
            {
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at.isoformat(),
            }
            for msg in messages
        ],
    }
