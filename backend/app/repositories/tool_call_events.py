# 模块说明：后端仓储模块，封装数据库读写细节并保持用户数据隔离。
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ToolCallStatus
from app.models.tool_call_event import ToolCallEvent


async def create_tool_call_event(
    session: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    tool_name: str,
    arguments: dict | None,
    message_id: uuid.UUID | None = None,
) -> ToolCallEvent:
    """函数作用：记录工具调用开始事件。
    输入参数：session - 异步数据库会话；user_id - 当前用户 UUID；conversation_id - 会话 UUID；tool_name - 工具名称；arguments - 工具参数；message_id - 关联消息 UUID。
    输出参数：工具调用事件。
    """
    event = ToolCallEvent(
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message_id,
        tool_name=tool_name,
        arguments=arguments,
        status=ToolCallStatus.STARTED,
    )
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return event


async def mark_tool_call_succeeded(
    session: AsyncSession,
    event: ToolCallEvent,
    result: dict | None,
) -> ToolCallEvent:
    """函数作用：标记工具调用成功。
    输入参数：session - 异步数据库会话；event - 工具调用事件；result - 工具结果。
    输出参数：更新后的工具调用事件。
    """
    event.status = ToolCallStatus.SUCCEEDED
    event.result = result
    event.finished_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(event)
    return event


async def mark_tool_call_failed(
    session: AsyncSession,
    event: ToolCallEvent,
    error: str,
) -> ToolCallEvent:
    """函数作用：标记工具调用失败。
    输入参数：session - 异步数据库会话；event - 工具调用事件；error - 错误信息。
    输出参数：更新后的工具调用事件。
    """
    event.status = ToolCallStatus.FAILED
    event.error = error
    event.finished_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(event)
    return event
