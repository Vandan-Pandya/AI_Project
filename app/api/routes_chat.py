"""
EduMentor AI Study Chat Router (1 Endpoint: /chat).
"""

from __future__ import annotations
from fastapi import APIRouter, HTTPException
from app.schemas.schemas import ChatRequest, ChatResponse
from app.services import llm_service

router = APIRouter(tags=["EduMentor Study Chat"])


@router.post("/chat", response_model=ChatResponse, summary="4. Ask EduMentor academic study questions")
async def chat(req: ChatRequest) -> ChatResponse:
    """
    Direct academic assistant with syllabus guardrails and off-topic redirection.
    """
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    answer = await llm_service.generate_text(req.message, history=req.history)
    return ChatResponse(answer=answer)
