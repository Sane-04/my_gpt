# 模块说明：后端测试模块，验证接口契约、仓储行为和核心服务边界。
import asyncio
import uuid
from datetime import datetime, timezone

from app.models.enums import MessageRole
from app.models.message import Message
from app.repositories import messages as messages_repository


def build_message(user_id: uuid.UUID, conversation_id: uuid.UUID, content: str, minute: int = 0) -> Message:
    """函数作用：构造混合检索测试消息。
    输入参数：user_id - 所属用户 UUID；conversation_id - 会话 UUID；content - 消息正文；minute - 创建时间分钟。
    输出参数：Message 模型实例。
    """
    message = Message(user_id=user_id, conversation_id=conversation_id, role=MessageRole.USER, content=content)
    message.id = uuid.uuid4()
    message.created_at = datetime(2026, 5, 18, 10, minute, tzinfo=timezone.utc)
    return message


def test_hybrid_search_session_memory_deduplicates_and_excludes_window(monkeypatch):
    """函数作用：验证 RRF 混合检索会去重、排除窗口内消息并保持用户和会话隔离参数。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    user_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    excluded_message = build_message(user_id, conversation_id, "窗口内")
    fts_message = build_message(user_id, conversation_id, "关键词命中")
    shared_message = build_message(user_id, conversation_id, "重复命中")
    embedding_message = build_message(user_id, conversation_id, "语义命中")
    calls = []

    async def _helper_search_messages_by_fts(session, captured_user_id, captured_conversation_id, query, limit, exclude_ids):
        calls.append(("fts", session, captured_user_id, captured_conversation_id, query, limit, exclude_ids))
        return [excluded_message, fts_message, shared_message]

    async def _helper_search_messages_by_embedding(
        session,
        captured_user_id,
        captured_conversation_id,
        query_embedding,
        limit,
        exclude_ids,
    ):
        calls.append(("embedding", session, captured_user_id, captured_conversation_id, query_embedding, limit, exclude_ids))
        return [shared_message, embedding_message]

    monkeypatch.setattr(messages_repository, "search_messages_by_fts", _helper_search_messages_by_fts)
    monkeypatch.setattr(messages_repository, "search_messages_by_embedding", _helper_search_messages_by_embedding)

    result = asyncio.run(
        messages_repository.hybrid_search_session_memory(
            session=object(),
            query="测试",
            conversation_id=conversation_id,
            user_id=user_id,
            limit=3,
            query_embedding=[0.1, 0.2, 0.3],
            exclude_message_ids={excluded_message.id},
        )
    )

    assert result == [shared_message, fts_message, embedding_message]
    assert len({message.id for message in result}) == 3
    assert excluded_message not in result
    assert calls[0][2] == user_id
    assert calls[0][3] == conversation_id
    assert calls[1][2] == user_id
    assert calls[1][3] == conversation_id


def test_hybrid_search_session_memory_uses_rrf_instead_of_fts_first(monkeypatch):
    """函数作用：验证 FTS 满额时，embedding 高排名结果仍可通过 RRF 进入最终结果。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    user_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    fts_top = build_message(user_id, conversation_id, "关键词第一", 1)
    fts_second = build_message(user_id, conversation_id, "关键词第二", 2)
    embedding_top = build_message(user_id, conversation_id, "语义第一", 3)

    async def _helper_search_messages_by_fts(*_args):
        return [fts_top, fts_second]

    async def _helper_search_messages_by_embedding(*_args):
        return [embedding_top, fts_second]

    monkeypatch.setattr(messages_repository, "search_messages_by_fts", _helper_search_messages_by_fts)
    monkeypatch.setattr(messages_repository, "search_messages_by_embedding", _helper_search_messages_by_embedding)

    result = asyncio.run(
        messages_repository.hybrid_search_session_memory(
            session=object(),
            query="测试",
            conversation_id=conversation_id,
            user_id=user_id,
            limit=2,
            query_embedding=[0.1, 0.2, 0.3],
        )
    )

    assert result == [fts_second, embedding_top]
    assert fts_top not in result
