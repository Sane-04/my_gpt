# 模块说明：后端 API 路由模块，负责请求校验、鉴权依赖和响应契约转换。
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.errors import AppError
from app.db import get_db
from app.models.enums import MemoryEventType
from app.models.long_term_memory import LongTermMemory
from app.models.user import User
from app.repositories.long_term_memories import (
    create_long_term_memory,
    delete_long_term_memory,
    get_memory_key,
    get_memory_source,
    get_memory_title,
    get_long_term_memory_by_id,
    list_long_term_memories,
    update_long_term_memory,
)
from app.repositories.memory_events import create_memory_event
from app.schemas.memory import (
    DeleteMemoryResponse,
    MemoryCreateRequest,
    MemoryDetailResponse,
    MemoryListResponse,
    MemoryResponse,
    MemoryUpdateRequest,
)
from app.services.memory_markdown import sync_long_term_memory_markdown


router = APIRouter(prefix="/api/memories", tags=["memories"])


def _parse_memory_id(memory_id: str) -> uuid.UUID:
    """函数作用：解析长期记忆 UUID。
    输入参数：memory_id - 前端传入的记忆 ID。
    输出参数：解析后的 UUID。
    """
    try:
        return uuid.UUID(memory_id)
    except ValueError:
        raise AppError(status_code=400, code="INVALID_MEMORY_INPUT", message="长期记忆 ID 格式不正确")


def _validate_memory_payload(title: str, memory_key: str, content: str) -> tuple[str, str, str]:
    """函数作用：校验并规范化长期记忆输入。
    输入参数：title - 标题；memory_key - 记忆键；content - 正文。
    输出参数：去空白后的三元组。
    """
    normalized_title = title.strip()
    normalized_key = memory_key.strip()
    normalized_content = content.strip()
    if not normalized_title or not normalized_key or not normalized_content:
        raise AppError(status_code=400, code="INVALID_MEMORY_INPUT", message="长期记忆标题、memory_key 和内容不能为空")

    return normalized_title, normalized_key, normalized_content


def _to_memory_response(memory: LongTermMemory) -> MemoryResponse:
    """函数作用：把长期记忆模型转换为前端响应。
    输入参数：memory - 长期记忆模型。
    输出参数：MemoryResponse。
    """
    return MemoryResponse(
        id=str(memory.id),
        title=get_memory_title(memory),
        memoryKey=get_memory_key(memory),
        content=memory.content,
        source=get_memory_source(memory),
        createdAt=memory.created_at.isoformat(),
        updatedAt=memory.updated_at.isoformat(),
    )


async def _sync_user_memory_markdown(session: AsyncSession, user_id: uuid.UUID) -> None:
    """函数作用：按数据库当前状态同步用户长期记忆 Markdown 副本。
    输入参数：session - 异步数据库会话；user_id - 当前用户 UUID。
    输出参数：无返回值。
    """
    settings = get_settings()
    memories = await list_long_term_memories(session, user_id)
    sync_long_term_memory_markdown(settings.memory_dir, user_id, memories)


@router.get("", response_model=MemoryListResponse)
async def list_memories(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> MemoryListResponse:
    """函数作用：获取当前用户长期记忆列表。
    输入参数：current_user - 当前登录用户；session - 异步数据库会话。
    输出参数：长期记忆列表响应。
    """
    memories = await list_long_term_memories(session, current_user.id)
    return MemoryListResponse(memories=[_to_memory_response(memory) for memory in memories])


@router.post("", response_model=MemoryDetailResponse)
async def create_memory(
    request: MemoryCreateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> MemoryDetailResponse:
    """函数作用：创建当前用户长期记忆。
    输入参数：request - 创建请求；current_user - 当前登录用户；session - 异步数据库会话。
    输出参数：创建后的长期记忆响应。
    """
    title, memory_key, content = _validate_memory_payload(request.title, request.memory_key, request.content)
    memory = await create_long_term_memory(
        session,
        current_user.id,
        title,
        memory_key,
        content,
        request.source or "manual",
    )
    await create_memory_event(
        session,
        current_user.id,
        MemoryEventType.CREATED,
        memory_id=memory.id,
        payload={"source": "api", "memory_key": memory_key},
    )
    await _sync_user_memory_markdown(session, current_user.id)
    return MemoryDetailResponse(memory=_to_memory_response(memory))


@router.put("/{memory_id}", response_model=MemoryDetailResponse)
async def update_memory(
    memory_id: str,
    request: MemoryUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> MemoryDetailResponse:
    """函数作用：更新当前用户长期记忆。
    输入参数：memory_id - 长期记忆 ID；request - 更新请求；current_user - 当前登录用户；session - 异步数据库会话。
    输出参数：更新后的长期记忆响应。
    """
    parsed_memory_id = _parse_memory_id(memory_id)
    title, memory_key, content = _validate_memory_payload(request.title, request.memory_key, request.content)
    memory = await update_long_term_memory(
        session,
        current_user.id,
        parsed_memory_id,
        title,
        memory_key,
        content,
        request.source or "manual",
    )
    if memory is None:
        raise AppError(status_code=404, code="MEMORY_NOT_FOUND", message="长期记忆不存在")

    await create_memory_event(
        session,
        current_user.id,
        MemoryEventType.UPDATED,
        memory_id=memory.id,
        payload={"source": "api", "memory_key": memory_key},
    )
    await _sync_user_memory_markdown(session, current_user.id)
    return MemoryDetailResponse(memory=_to_memory_response(memory))


@router.delete("/{memory_id}", response_model=DeleteMemoryResponse)
async def delete_memory(
    memory_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> DeleteMemoryResponse:
    """函数作用：删除当前用户长期记忆。
    输入参数：memory_id - 长期记忆 ID；current_user - 当前登录用户；session - 异步数据库会话。
    输出参数：删除响应。
    """
    parsed_memory_id = _parse_memory_id(memory_id)
    memory = await get_long_term_memory_by_id(session, current_user.id, parsed_memory_id)
    if memory is None:
        raise AppError(status_code=404, code="MEMORY_NOT_FOUND", message="长期记忆不存在")

    await create_memory_event(
        session,
        current_user.id,
        MemoryEventType.DELETED,
        memory_id=memory.id,
        payload={"source": "api", "memory_key": get_memory_key(memory), "content": memory.content},
    )
    deleted = await delete_long_term_memory(session, current_user.id, parsed_memory_id)
    if not deleted:
        raise AppError(status_code=404, code="MEMORY_NOT_FOUND", message="长期记忆不存在")

    await _sync_user_memory_markdown(session, current_user.id)
    return DeleteMemoryResponse(deleted_id=str(parsed_memory_id))
