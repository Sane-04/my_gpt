# 模块说明：后端仓储模块，封装数据库读写细节并保持用户数据隔离。
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.message import Message


async def create_conversation(session: AsyncSession, user_id: uuid.UUID, title: str | None) -> Conversation:
    """函数作用：创建当前用户的新会话。
    输入参数：session - 异步数据库会话；user_id - 当前用户 UUID；title - 可选会话标题。
    输出参数：返回已刷新主键和时间字段的 Conversation。
    """
    normalized_title = title.strip() if title else ""
    conversation = Conversation(user_id=user_id, title=normalized_title or "新的对话")
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return conversation


async def list_conversations(session: AsyncSession, user_id: uuid.UUID) -> list[Conversation]:
    """函数作用：按更新时间倒序读取当前用户会话列表。
    输入参数：session - 异步数据库会话；user_id - 当前用户 UUID。
    输出参数：返回当前用户的 Conversation 列表。
    """
    result = await session.execute(
        select(Conversation).where(Conversation.user_id == user_id).order_by(desc(Conversation.updated_at))
    )
    return list(result.scalars().all())


async def get_conversation_by_id(
    session: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> Conversation | None:
    """函数作用：按会话 ID 读取当前用户自己的会话。
    输入参数：session - 异步数据库会话；user_id - 当前用户 UUID；conversation_id - 会话 UUID。
    输出参数：找到时返回 Conversation，否则返回 None。
    """
    result = await session.execute(
        select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def delete_conversation_by_id(
    session: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> bool:
    """函数作用：硬删除当前用户自己的会话及其消息。
    输入参数：session - 异步数据库会话；user_id - 当前用户 UUID；conversation_id - 会话 UUID。
    输出参数：删除成功返回 True；会话不存在或不属于当前用户返回 False。
    """
    conversation = await get_conversation_by_id(session, user_id, conversation_id)
    if conversation is None:
        return False

    await session.execute(delete(Message).where(Message.conversation_id == conversation_id, Message.user_id == user_id))
    await session.delete(conversation)
    await session.commit()
    return True


async def update_conversation_title(
    session: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    title: str,
) -> Conversation | None:
    """函数作用：更新当前用户自己的会话标题。
    输入参数：session - 异步数据库会话；user_id - 当前用户 UUID；conversation_id - 会话 UUID；title - 新标题。
    输出参数：找到并更新时返回 Conversation，否则返回 None。
    """
    conversation = await get_conversation_by_id(session, user_id, conversation_id)
    if conversation is None:
        return None

    conversation.title = title[:200]
    conversation.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(conversation)
    return conversation
