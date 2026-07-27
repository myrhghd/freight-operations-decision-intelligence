from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.rag.retriever import extractive_answer_from_chunks, retrieve_sop_chunks
from app.services.assistant_service import build_chat_response


router = APIRouter(prefix="/assistant", tags=["assistant"])


class SopSearchRequest(BaseModel):
    question: str = Field(..., min_length=3)


class AssistantChatRequest(BaseModel):
    question: str = Field(..., min_length=3)


@router.post("/sop-search")
def sop_search(payload: SopSearchRequest) -> dict:
    chunks = retrieve_sop_chunks(question=payload.question, top_k=3)
    result = extractive_answer_from_chunks(question=payload.question, chunks=chunks)
    return result


@router.post("/chat")
def assistant_chat(payload: AssistantChatRequest) -> dict:
    return build_chat_response(payload.question)
