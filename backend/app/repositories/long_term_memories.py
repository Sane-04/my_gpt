# 模块说明：后端仓储模块，封装数据库读写细节并保持用户数据隔离。
import uuid
from datetime import datetime, timezone

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.long_term_memory import LongTermMemory


def _build_memory_metadata(title: str, memory_key: str, source: str | None) -> dict:
    """函数作用：构造长期记忆 metadata 字段。
    输入参数：title - 标题；memory_key - 记忆键；source - 来源。
    输出参数：metadata 字典。
    """
    return {
        "title": title.strip(),
        "memory_key": memory_key.strip(),
        "source": (source or "manual").strip() or "manual",
    }


def get_memory_title(memory: LongTermMemory) -> str:
    """函数作用：读取长期记忆标题。
    输入参数：memory - 长期记忆模型。
    输出参数：标题文本。
    """
    metadata = memory.metadata_ or {}
    return str(metadata.get("title") or "长期记忆")


def get_memory_key(memory: LongTermMemory) -> str:
    """函数作用：读取长期记忆 memory_key。
    输入参数：memory - 长期记忆模型。
    输出参数：memory_key 文本。
    """
    metadata = memory.metadata_ or {}
    return str(metadata.get("memory_key") or str(memory.id))


def get_memory_source(memory: LongTermMemory) -> str:
    """函数作用：读取长期记忆来源。
    输入参数：memory - 长期记忆模型。
    输出参数：来源文本。
    """
    metadata = memory.metadata_ or {}
    return str(metadata.get("source") or "manual")


async def list_long_term_memories(session: AsyncSession, user_id: uuid.UUID) -> list[LongTermMemory]:
    """函数作用：按更新时间倒序读取当前用户长期记忆。
    输入参数：session - 异步数据库会话；user_id - 当前用户 UUID。
    输出参数：长期记忆列表。
    """
    result = await session.execute(
        select(LongTermMemory)
        .where(LongTermMemory.user_id == user_id)
        .order_by(desc(LongTermMemory.updated_at), desc(LongTermMemory.created_at))
    )
    return list(result.scalars().all())


async def get_long_term_memory_by_id(
    session: AsyncSession,
    user_id: uuid.UUID,
    memory_id: uuid.UUID,
) -> LongTermMemory | None:
    """函数作用：按 ID 读取当前用户长期记忆。
    输入参数：session - 异步数据库会话；user_id - 当前用户 UUID；memory_id - 长期记忆 UUID。
    输出参数：长期记忆或 None。
    """
    memory = await session.get(LongTermMemory, memory_id)
    if memory is None or memory.user_id != user_id:
        return None

    return memory


async def get_long_term_memory_by_key(
    session: AsyncSession,
    user_id: uuid.UUID,
    memory_key: str,
) -> LongTermMemory | None:
    """函数作用：按 memory_key 读取当前用户长期记忆。
    输入参数：session - 异步数据库会话；user_id - 当前用户 UUID；memory_key - 记忆键。
    输出参数：长期记忆或 None。
    """
    memories = await list_long_term_memories(session, user_id)
    normalized_key = memory_key.strip()
    for memory in memories:
        if get_memory_key(memory) == normalized_key:
            return memory

    return None


async def create_long_term_memory(
    session: AsyncSession,
    user_id: uuid.UUID,
    title: str,
    memory_key: str,
    content: str,
    source: str | None = "manual",
    source_message_id: uuid.UUID | None = None,
) -> LongTermMemory:
    """函数作用：创建当前用户长期记忆。
    输入参数：session - 异步数据库会话；user_id - 当前用户 UUID；title - 标题；memory_key - 记忆键；content - 正文；source - 来源；source_message_id - 来源消息 UUID。
    输出参数：创建后的长期记忆。
    """
    memory = LongTermMemory(
        user_id=user_id,
        source_message_id=source_message_id,
        content=content.strip(),
        metadata_=_build_memory_metadata(title, memory_key, source),
    )
    session.add(memory)
    await session.commit()
    await session.refresh(memory)
    return memory


async def update_long_term_memory(
    session: AsyncSession,
    user_id: uuid.UUID,
    memory_id: uuid.UUID,
    title: str,
    memory_key: str,
    content: str,
    source: str | None = "manual",
) -> LongTermMemory | None:
    """函数作用：更新当前用户长期记忆。
    输入参数：session - 异步数据库会话；user_id - 当前用户 UUID；memory_id - 长期记忆 UUID；title - 标题；memory_key - 记忆键；content - 正文；source - 来源。
    输出参数：更新后的长期记忆或 None。
    """
    memory = await get_long_term_memory_by_id(session, user_id, memory_id)
    if memory is None:
        return None

    memory.content = content.strip()
    memory.metadata_ = _build_memory_metadata(title, memory_key, source)
    memory.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(memory)
    return memory


async def delete_long_term_memory(session: AsyncSession, user_id: uuid.UUID, memory_id: uuid.UUID) -> bool:
    """函数作用：删除当前用户长期记忆。
    输入参数：session - 异步数据库会话；user_id - 当前用户 UUID；memory_id - 长期记忆 UUID。
    输出参数：删除成功返回 True，不存在返回 False。
    """
    memory = await get_long_term_memory_by_id(session, user_id, memory_id)
    if memory is None:
        return False

    await session.delete(memory)
    await session.commit()
    return True


def format_long_term_memories_for_prompt(memories: list[LongTermMemory], max_chars: int) -> str:
    """函数作用：把长期记忆格式化为可注入模型的全文。
    输入参数：memories - 长期记忆列表；max_chars - 最大字符数。
    输出参数：格式化后的长期记忆文本。
    """
    if max_chars <= 0 or not memories:
        return ""

    sections = []
    for memory in memories:
        sections.append(f"- {get_memory_title(memory)} ({get_memory_key(memory)}): {memory.content}")

    content = "\n".join(sections)
    if len(content) <= max_chars:
        return content

    return f"{content[:max_chars]}\n[长期记忆已按字符上限截断]"
