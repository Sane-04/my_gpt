# 模块说明：后端仓储模块，封装数据库读写细节并保持用户数据隔离。
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prompt_snapshot import PromptSnapshot


async def create_prompt_snapshot(
    session: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    request_message_id: uuid.UUID | None,
    model: str,
    prompt: str,
    messages: list[dict[str, str]],
    metadata: dict | None = None,
) -> PromptSnapshot:
    """函数作用：保存一次模型请求 Prompt 快照。
    输入参数：session - 异步数据库会话；user_id - 用户 UUID；conversation_id - 会话 UUID；request_message_id - 触发消息 UUID；model - 模型名；prompt - 最终 prompt 文本；messages - 结构化消息；metadata - 扩展信息。
    输出参数：返回已刷新的 PromptSnapshot。
    """
    snapshot = PromptSnapshot(
        user_id=user_id,
        conversation_id=conversation_id,
        request_message_id=request_message_id,
        model=model,
        prompt=prompt,
        messages=messages,
        metadata_=metadata,
    )
    session.add(snapshot)
    await session.commit()
    await session.refresh(snapshot)
    return snapshot
