# 模块说明：后端仓储模块，封装数据库读写细节并保持用户数据隔离。
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import MemoryEventType
from app.models.memory_event import MemoryEvent


async def create_memory_event(
    session: AsyncSession,
    user_id: uuid.UUID,
    event_type: MemoryEventType,
    memory_id: uuid.UUID | None = None,
    message_id: uuid.UUID | None = None,
    payload: dict | None = None,
) -> MemoryEvent:
    """函数作用：创建长期记忆事件。
    输入参数：session - 异步数据库会话；user_id - 当前用户 UUID；event_type - 事件类型；memory_id - 记忆 UUID；message_id - 来源消息 UUID；payload - 事件载荷。
    输出参数：已保存的 MemoryEvent。
    """
    event = MemoryEvent(
        user_id=user_id,
        memory_id=memory_id,
        message_id=message_id,
        event_type=event_type,
        payload=payload,
    )
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return event
