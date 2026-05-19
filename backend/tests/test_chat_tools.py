# 模块说明：后端测试模块，验证接口契约、仓储行为和核心服务边界。
import asyncio
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from app.models.enums import MessageRole, ToolCallStatus
from app.repositories.tool_call_events import create_tool_call_event, mark_tool_call_succeeded
from app.tools import chat_tools


class FakeSession:
    """类作用：模拟工具测试 Session。"""

    def __init__(self):
        """函数作用：初始化模拟状态。
        输入参数：无。
        输出参数：无返回值。
        """
        self.added = []
        self.committed = False
        self.refreshed = []

    def add(self, item):
        """函数作用：记录新增对象。
        输入参数：item - 待新增对象。
        输出参数：无返回值。
        """
        self.added.append(item)

    async def commit(self):
        """函数作用：记录事务提交。
        输入参数：无。
        输出参数：无返回值。
        """
        self.committed = True

    async def refresh(self, item):
        """函数作用：模拟刷新。
        输入参数：item - 待刷新对象。
        输出参数：无返回值。
        """
        item.id = getattr(item, "id", None) or uuid.uuid4()
        self.refreshed.append(item)


class FakeModelClient:
    """类作用：模拟模型客户端。"""

    async def create_embedding(self, _text):
        """函数作用：返回固定向量。
        输入参数：_text - 查询文本。
        输出参数：固定向量。
        """
        return [0.1, 0.2, 0.3]


def test_tool_call_event_can_be_marked_succeeded():
    """函数作用：验证工具调用审计可记录成功结果。
    输入参数：无。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    session = FakeSession()
    user_id = uuid.uuid4()
    conversation_id = uuid.uuid4()

    event = asyncio.run(create_tool_call_event(session, user_id, conversation_id, "list_long_term_memory", {"limit": 1}))
    updated_event = asyncio.run(mark_tool_call_succeeded(session, event, {"ok": True}))

    assert event in session.added
    assert updated_event.status == ToolCallStatus.SUCCEEDED
    assert updated_event.result == {"ok": True}
    assert updated_event.finished_at is not None


def test_execute_search_session_memory_tool(monkeypatch):
    """函数作用：验证 search_session_memory 工具会调用当前会话混合检索。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    user_id = uuid.uuid4()
    conversation_id = uuid.uuid4()

    async def _helper_hybrid_search_session_memory(**kwargs):
        return []

    monkeypatch.setattr(chat_tools, "hybrid_search_session_memory", _helper_hybrid_search_session_memory)

    result = asyncio.run(
        chat_tools.execute_chat_tool(
            session=FakeSession(),
            model_client=FakeModelClient(),
            user_id=user_id,
            conversation_id=conversation_id,
            tool_name="search_session_memory",
            arguments={"query": "数据库", "limit": 3},
        )
    )

    assert result == {"messages": []}


def test_execute_get_session_messages_by_position_tool(monkeypatch):
    """函数作用：验证 get_session_messages_by_position 工具按时间线位置读取会话消息。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    user_id = uuid.uuid4()
    conversation_id = uuid.uuid4()
    message_id = uuid.uuid4()
    created_at = datetime(2026, 5, 18, 12, 0, tzinfo=timezone.utc)
    calls = []

    async def _helper_list_messages_by_chronological_position(**kwargs):
        calls.append(kwargs)
        return [
            SimpleNamespace(
                id=message_id,
                role=MessageRole.USER,
                content="记住，我喜欢陈言",
                created_at=created_at,
            )
        ]

    monkeypatch.setattr(
        chat_tools,
        "list_messages_by_chronological_position",
        _helper_list_messages_by_chronological_position,
    )

    result = asyncio.run(
        chat_tools.execute_chat_tool(
            session=FakeSession(),
            model_client=FakeModelClient(),
            user_id=user_id,
            conversation_id=conversation_id,
            tool_name="get_session_messages_by_position",
            arguments={"position": "earliest", "role": "user", "offset": 0, "limit": 1},
        )
    )

    assert calls == [
        {
            "session": calls[0]["session"],
            "user_id": user_id,
            "conversation_id": conversation_id,
            "position": "earliest",
            "limit": 1,
            "offset": 0,
            "role": MessageRole.USER,
        }
    ]
    assert result == {
        "position": "earliest",
        "role": "user",
        "offset": 0,
        "messages": [
            {
                "id": str(message_id),
                "role": "user",
                "content": "记住，我喜欢陈言",
                "created_at": "2026-05-18T12:00:00+00:00",
                "relative_position": 1,
            }
        ],
    }


def test_execute_web_search_tool(monkeypatch):
    """函数作用：验证 web_search 工具会返回带来源链接的结构化搜索结果。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    user_id = uuid.uuid4()
    conversation_id = uuid.uuid4()

    class FakeResponse:
        """类作用：模拟 SerpApi HTTP 响应。"""

        status_code = 200

        def json(self):
            """函数作用：返回 SerpApi 风格 JSON。
            输入参数：无。
            输出参数：响应 JSON。
            """
            return {
                "organic_results": [
                    {
                        "title": "OpenAI News",
                        "link": "https://example.com/openai-news",
                        "displayed_link": "example.com",
                        "snippet": "模型新闻摘要",
                    }
                ]
            }

    class FakeAsyncClient:
        """类作用：模拟 httpx.AsyncClient。"""

        async def __aenter__(self):
            """函数作用：进入异步上下文管理器。
            输入参数：无。
            输出参数：当前模拟对象。
            """
            return self

        async def __aexit__(self, _exc_type, _exc, _traceback):
            """函数作用：退出异步上下文管理器。
            输入参数：_exc_type、_exc、_traceback - 上下文异常信息。
            输出参数：False，表示不吞掉异常。
            """
            return False

        async def get(self, url, params):
            """函数作用：断言 SerpApi 请求参数并返回模拟响应。
            输入参数：url - 请求地址；params - 查询参数。
            输出参数：FakeResponse。
            """
            assert url == "https://serpapi.com/search.json"
            assert params["engine"] == "google"
            assert params["q"] == "OpenAI 最新模型"
            assert params["api_key"] == "serp-key"
            assert params["num"] == 3
            assert params["hl"] == "zh-cn"
            return FakeResponse()

    monkeypatch.setattr(chat_tools.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(
        chat_tools,
        "get_settings",
        lambda: SimpleNamespace(serpapi_api_key="serp-key"),
    )

    result = asyncio.run(
        chat_tools.execute_chat_tool(
            session=FakeSession(),
            model_client=FakeModelClient(),
            user_id=user_id,
            conversation_id=conversation_id,
            tool_name="web_search",
            arguments={"query": "OpenAI 最新模型", "limit": 3},
        )
    )

    assert result["query"] == "OpenAI 最新模型"
    assert result["results"] == [
        {
            "id": "src_1",
            "title": "OpenAI News",
            "url": "https://example.com/openai-news",
            "domain": "example.com",
            "snippet": "模型新闻摘要",
            "source": "serpapi",
        }
    ]
    assert "[[cite:src_1]]" in result["instruction"]


def test_execute_web_search_tool_requires_serpapi_key(monkeypatch):
    """函数作用：验证未配置 SerpApi API Key 时返回清晰错误。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    monkeypatch.setattr(
        chat_tools,
        "get_settings",
        lambda: SimpleNamespace(serpapi_api_key=""),
    )

    result = asyncio.run(
        chat_tools.execute_chat_tool(
            session=FakeSession(),
            model_client=FakeModelClient(),
            user_id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            tool_name="web_search",
            arguments={"query": "OpenAI 最新模型", "limit": 3},
        )
    )

    assert result == {"error": "SERPAPI_API_KEY 未配置"}
