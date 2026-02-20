from typing import Literal

from pydantic import BaseModel, Field


Role = Literal["system", "user", "assistant"]


class ChatMessage(BaseModel):
    role: Role
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    history: list[ChatMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    reply: str
    model: str
    latency_ms: int


class ErrorResponse(BaseModel):
    detail: str


class EmbedTokenRequest(BaseModel):
    chatbot_id: str = Field(min_length=1, max_length=100)


class EmbedTokenResponse(BaseModel):
    token: str
    token_type: str = "Bearer"
    expires_in: int
