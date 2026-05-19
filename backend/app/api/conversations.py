# 模块说明：后端 API 路由模块，负责请求校验、鉴权依赖和响应契约转换。
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.errors import AppError
from app.db import get_db
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.repositories.conversations import (
    create_conversation,
    delete_conversation_by_id,
    get_conversation_by_id,
    list_conversations,
)
from app.repositories.messages import list_messages_page
from app.schemas.conversation import (
    ConversationCreateRequest,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationMessagesResponse,
    ConversationResponse,
    DeleteConversationResponse,
    MessageResponse,
)


router = APIRouter(prefix="/api/conversations", tags=["conversations"])
MESSAGE_PAGE_SIZE = 20


def _serialize_conversation(conversation: Conversation) -> ConversationResponse:
    """函数作用：把会话模型转换为前端 Conversation 契约。
    输入参数：conversation - 数据库会话模型。
    输出参数：ConversationResponse。
    """
    return ConversationResponse(
        id=str(conversation.id),
        title=conversation.title or "新的对话",
        createdAt=conversation.created_at.isoformat() if conversation.created_at else None,
        updatedAt=conversation.updated_at.isoformat(),
    )


def _serialize_message(message: Message) -> MessageResponse:
    """函数作用：把消息模型转换为前端 Message 契约。
    输入参数：message - 数据库消息模型。
    输出参数：MessageResponse。
    """
    metadata = message.metadata_ or {}
    tool_name = metadata.get("toolName") if isinstance(metadata, dict) else None
    images = metadata.get("images") if isinstance(metadata, dict) else None
    sources = metadata.get("sources") if isinstance(metadata, dict) else None
    citation_groups = metadata.get("citationGroups") if isinstance(metadata, dict) else None

    return MessageResponse(
        id=str(message.id),
        conversationId=str(message.conversation_id),
        role=message.role.value,
        content=message.content,
        createdAt=message.created_at.isoformat(),
        status="complete",
        toolName=tool_name,
        images=images if isinstance(images, list) else None,
        sources=sources if isinstance(sources, list) else None,
        citationGroups=citation_groups if isinstance(citation_groups, list) else None,
    )


def _parse_conversation_id(conversation_id: str) -> uuid.UUID:
    """函数作用：解析 URL 中的会话 UUID。
    输入参数：conversation_id - URL 路径中的会话 ID 字符串。
    输出参数：解析后的 UUID；格式错误时抛出 AppError。
    """
    try:
        return uuid.UUID(conversation_id)
    except ValueError:
        raise AppError(status_code=404, code="CONVERSATION_NOT_FOUND", message="会话不存在")


@router.post("", response_model=ConversationDetailResponse)
async def create_conversation_endpoint(
    request: ConversationCreateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ConversationDetailResponse:
    """函数作用：创建当前用户的新会话。
    输入参数：request - 创建会话请求体；current_user - 当前登录用户；session - 异步数据库会话。
    输出参数：ConversationDetailResponse。
    """
    title = request.title.strip() if request.title else None
    if title == "":
        raise AppError(status_code=400, code="INVALID_CONVERSATION_INPUT", message="会话标题不能为空")

    conversation = await create_conversation(session, current_user.id, title)
    return ConversationDetailResponse(conversation=_serialize_conversation(conversation))


@router.get("", response_model=ConversationListResponse)
async def list_conversations_endpoint(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ConversationListResponse:
    """函数作用：读取当前用户会话列表。
    输入参数：current_user - 当前登录用户；session - 异步数据库会话。
    输出参数：ConversationListResponse。
    """
    conversations = await list_conversations(session, current_user.id)
    return ConversationListResponse(conversations=[_serialize_conversation(item) for item in conversations])


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation_endpoint(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ConversationDetailResponse:
    """函数作用：读取当前用户指定会话详情。
    输入参数：conversation_id - 会话 ID；current_user - 当前登录用户；session - 异步数据库会话。
    输出参数：ConversationDetailResponse。
    """
    parsed_conversation_id = _parse_conversation_id(conversation_id)
    conversation = await get_conversation_by_id(session, current_user.id, parsed_conversation_id)
    if conversation is None:
        raise AppError(status_code=404, code="CONVERSATION_NOT_FOUND", message="会话不存在")

    return ConversationDetailResponse(conversation=_serialize_conversation(conversation))


@router.delete("/{conversation_id}", response_model=DeleteConversationResponse)
async def delete_conversation_endpoint(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> DeleteConversationResponse:
    """函数作用：硬删除当前用户指定会话及其消息。
    输入参数：conversation_id - 会话 ID；current_user - 当前登录用户；session - 异步数据库会话。
    输出参数：DeleteConversationResponse。
    """
    parsed_conversation_id = _parse_conversation_id(conversation_id)
    deleted = await delete_conversation_by_id(session, current_user.id, parsed_conversation_id)
    if not deleted:
        raise AppError(status_code=404, code="CONVERSATION_NOT_FOUND", message="会话不存在")

    return DeleteConversationResponse(deleted_id=conversation_id)


@router.get("/{conversation_id}/messages", response_model=ConversationMessagesResponse)
async def get_conversation_messages_endpoint(
    conversation_id: str,
    limit: int = Query(default=MESSAGE_PAGE_SIZE, ge=1, le=100),
    before: datetime | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ConversationMessagesResponse:
    """函数作用：读取当前用户指定会话的消息列表。
    输入参数：conversation_id - 会话 ID；limit - 每页数量；before - 更早消息游标；current_user - 当前登录用户；session - 异步数据库会话。
    输出参数：ConversationMessagesResponse。
    """
    parsed_conversation_id = _parse_conversation_id(conversation_id)
    conversation = await get_conversation_by_id(session, current_user.id, parsed_conversation_id)
    if conversation is None:
        raise AppError(status_code=404, code="CONVERSATION_NOT_FOUND", message="会话不存在")

    messages, has_more = await list_messages_page(session, current_user.id, parsed_conversation_id, limit, before)
    return ConversationMessagesResponse(messages=[_serialize_message(item) for item in messages], hasMore=has_more)
