# 模块说明：后端仓储模块，封装数据库读写细节并保持用户数据隔离。
import uuid
from datetime import datetime, timezone

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.enums import EmbeddingStatus, MessageRole
from app.models.message import Message


async def list_messages(session: AsyncSession, user_id: uuid.UUID, conversation_id: uuid.UUID) -> list[Message]:
    """函数作用：按创建时间正序读取当前用户指定会话的消息。
    输入参数：session - 异步数据库会话；user_id - 当前用户 UUID；conversation_id - 会话 UUID。
    输出参数：返回 Message 列表。
    """
    result = await session.execute(
        select(Message)
        .where(Message.user_id == user_id, Message.conversation_id == conversation_id)
        .order_by(asc(Message.created_at))
    )
    return list(result.scalars().all())


async def list_messages_page(
    session: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    limit: int,
    before: datetime | None = None,
) -> tuple[list[Message], bool]:
    """函数作用：分页读取当前用户指定会话消息，默认取最近一页。
    输入参数：session - 异步数据库会话；user_id - 当前用户 UUID；conversation_id - 会话 UUID；limit - 每页数量；before - 只读取该时间之前的更早消息。
    输出参数：返回按创建时间正序排列的 Message 列表，以及是否还有更早消息。
    """
    if limit <= 0:
        return [], False

    statement = select(Message).where(Message.user_id == user_id, Message.conversation_id == conversation_id)
    if before is not None:
        statement = statement.where(Message.created_at < before)

    result = await session.execute(statement.order_by(desc(Message.created_at)).limit(limit + 1))
    messages = list(result.scalars().all())
    has_more = len(messages) > limit
    return list(reversed(messages[:limit])), has_more


async def count_messages(session: AsyncSession, user_id: uuid.UUID, conversation_id: uuid.UUID) -> int:
    """函数作用：统计当前用户指定会话下的消息数量。
    输入参数：session - 异步数据库会话；user_id - 当前用户 UUID；conversation_id - 会话 UUID。
    输出参数：返回消息数量。
    """
    result = await session.execute(
        select(func.count())
        .select_from(Message)
        .where(Message.user_id == user_id, Message.conversation_id == conversation_id)
    )
    return int(result.scalar_one())


async def list_recent_messages(
    session: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    limit: int,
) -> list[Message]:
    """函数作用：读取当前用户指定会话最近 N 条消息并按时间正序返回。
    输入参数：session - 异步数据库会话；user_id - 当前用户 UUID；conversation_id - 会话 UUID；limit - 最近消息数量。
    输出参数：按创建时间正序排列的 Message 列表。
    """
    if limit <= 0:
        return []

    result = await session.execute(
        select(Message)
        .where(Message.user_id == user_id, Message.conversation_id == conversation_id)
        .order_by(desc(Message.created_at))
        .limit(limit)
    )
    return list(reversed(list(result.scalars().all())))


async def list_messages_by_chronological_position(
    session: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    position: str,
    limit: int,
    offset: int = 0,
    role: MessageRole | None = None,
) -> list[Message]:
    """函数作用：按当前会话时间线位置读取消息，适合回答第一句、最后一句等确定性问题。
    输入参数：session - 异步数据库会话；user_id - 当前用户 UUID；conversation_id - 会话 UUID；position - earliest 或 latest；limit - 返回数量；offset - 从边界跳过的消息数；role - 可选消息角色过滤。
    输出参数：按创建时间正序排列的 Message 列表。
    """
    if limit <= 0:
        return []

    safe_offset = max(offset, 0)
    statement = select(Message).where(Message.user_id == user_id, Message.conversation_id == conversation_id)
    if role is not None:
        statement = statement.where(Message.role == role)

    if position == "latest":
        result = await session.execute(statement.order_by(desc(Message.created_at)).offset(safe_offset).limit(limit))
        return list(reversed(list(result.scalars().all())))

    result = await session.execute(statement.order_by(asc(Message.created_at)).offset(safe_offset).limit(limit))
    return list(result.scalars().all())


async def update_message_embedding_result(
    session: AsyncSession,
    message_id: uuid.UUID,
    user_id: uuid.UUID,
    embedding: list[float] | None,
    status: EmbeddingStatus,
    error: str | None,
) -> Message | None:
    """函数作用：更新当前用户消息的 embedding 结果和状态。
    输入参数：session - 异步数据库会话；message_id - 消息 UUID；user_id - 当前用户 UUID；embedding - 向量结果；status - embedding 状态；error - 失败错误。
    输出参数：返回更新后的 Message；消息不存在或不属于当前用户时返回 None。
    """
    message = await session.get(Message, message_id)
    if message is None or message.user_id != user_id:
        return None

    message.embedding = embedding
    message.embedding_status = status
    message.embedding_error = error
    await session.commit()
    await session.refresh(message)
    return message


async def search_messages_by_fts(
    session: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    query: str,
    limit: int,
    exclude_message_ids: set[uuid.UUID] | None = None,
) -> list[Message]:
    """函数作用：使用 PostgreSQL FTS 检索当前会话窗口外历史消息。
    输入参数：session - 异步数据库会话；user_id - 当前用户 UUID；conversation_id - 会话 UUID；query - 检索词；limit - 返回数量；exclude_message_ids - 需要排除的消息 UUID 集合。
    输出参数：匹配的 Message 列表。
    """
    if limit <= 0 or not query.strip():
        return []

    ts_query = func.plainto_tsquery("simple", query)
    statement = (
        select(Message)
        .where(
            Message.user_id == user_id,
            Message.conversation_id == conversation_id,
            Message.fts_vector.op("@@")(ts_query),
        )
        .order_by(desc(func.ts_rank_cd(Message.fts_vector, ts_query)), desc(Message.created_at))
        .limit(limit)
    )
    if exclude_message_ids:
        statement = statement.where(Message.id.not_in(exclude_message_ids))

    result = await session.execute(statement)
    return list(result.scalars().all())


async def search_messages_by_embedding(
    session: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    query_embedding: list[float],
    limit: int,
    exclude_message_ids: set[uuid.UUID] | None = None,
) -> list[Message]:
    """函数作用：使用 pgvector 相似度检索当前会话窗口外历史消息。
    输入参数：session - 异步数据库会话；user_id - 当前用户 UUID；conversation_id - 会话 UUID；query_embedding - 查询向量；limit - 返回数量；exclude_message_ids - 需要排除的消息 UUID 集合。
    输出参数：语义相似的 Message 列表。
    """
    if limit <= 0 or not query_embedding:
        return []

    statement = (
        select(Message)
        .where(
            Message.user_id == user_id,
            Message.conversation_id == conversation_id,
            Message.embedding_status == EmbeddingStatus.COMPLETED,
            Message.embedding.is_not(None),
        )
        .order_by(Message.embedding.cosine_distance(query_embedding), desc(Message.created_at))
        .limit(limit)
    )
    if exclude_message_ids:
        statement = statement.where(Message.id.not_in(exclude_message_ids))

    result = await session.execute(statement)
    return list(result.scalars().all())


async def hybrid_search_session_memory(
    session: AsyncSession,
    query: str,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    limit: int,
    query_embedding: list[float] | None = None,
    exclude_message_ids: set[uuid.UUID] | None = None,
) -> list[Message]:
    """函数作用：使用 RRF 融合 FTS 与 embedding 检索当前会话窗口外历史消息。
    输入参数：session - 异步数据库会话；query - 检索词；conversation_id - 会话 UUID；user_id - 当前用户 UUID；limit - 返回数量；query_embedding - 可选查询向量；exclude_message_ids - 需要排除的消息 UUID 集合。
    输出参数：按 RRF 分数排序并去重后的 Message 列表。
    """
    if limit <= 0:
        return []

    rrf_k = 60
    exclude_ids = exclude_message_ids or set()
    fts_messages = await search_messages_by_fts(session, user_id, conversation_id, query, limit, exclude_ids)
    embedding_messages = []
    if query_embedding:
        embedding_messages = await search_messages_by_embedding(
            session,
            user_id,
            conversation_id,
            query_embedding,
            limit,
            exclude_ids,
        )

    ranked_candidates = {}
    for ranked_messages in [fts_messages, embedding_messages]:
        for rank, message in enumerate(ranked_messages, start=1):
            if message.id in exclude_ids:
                continue

            if message.id not in ranked_candidates:
                ranked_candidates[message.id] = {"message": message, "score": 0.0}

            ranked_candidates[message.id]["score"] += 1 / (rrf_k + rank)

    sorted_candidates = sorted(
        ranked_candidates.values(),
        key=lambda candidate: (candidate["score"], candidate["message"].created_at),
        reverse=True,
    )
    return [candidate["message"] for candidate in sorted_candidates[:limit]]


async def create_message(
    session: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    role: MessageRole,
    content: str,
    metadata: dict | None = None,
) -> Message:
    """函数作用：新增消息并同步触发会话 updated_at 更新。
    输入参数：session - 异步数据库会话；user_id - 当前用户 UUID；conversation_id - 会话 UUID；role - 消息角色；content - 消息正文；metadata - 可选扩展元数据。
    输出参数：返回已刷新主键和时间字段的 Message。
    """
    message = Message(
        user_id=user_id,
        conversation_id=conversation_id,
        role=role,
        content=content,
        metadata_=metadata,
    )
    session.add(message)

    conversation = await session.get(Conversation, conversation_id)
    if conversation is not None and conversation.user_id == user_id:
        conversation.updated_at = datetime.now(timezone.utc)

    await session.commit()
    await session.refresh(message)
    return message
