# 模块说明：后端 Pydantic 契约模块，定义请求体和响应体结构。
from app.schemas.auth import AuthResponse, LoginRequest, MeResponse, RegisterRequest, UserResponse
from app.schemas.chat import ChatStreamRequest
from app.schemas.conversation import (
    ConversationCreateRequest,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationMessagesResponse,
    ConversationResponse,
    DeleteConversationResponse,
    MessageResponse,
)
from app.schemas.memory import (
    DeleteMemoryResponse,
    MemoryCreateRequest,
    MemoryDetailResponse,
    MemoryListResponse,
    MemoryResponse,
    MemoryUpdateRequest,
)

__all__ = [
    "AuthResponse",
    "ChatStreamRequest",
    "ConversationCreateRequest",
    "ConversationDetailResponse",
    "ConversationListResponse",
    "ConversationMessagesResponse",
    "ConversationResponse",
    "DeleteConversationResponse",
    "DeleteMemoryResponse",
    "LoginRequest",
    "MeResponse",
    "MemoryCreateRequest",
    "MemoryDetailResponse",
    "MemoryListResponse",
    "MemoryResponse",
    "MemoryUpdateRequest",
    "MessageResponse",
    "RegisterRequest",
    "UserResponse",
]
