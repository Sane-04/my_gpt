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


def test_get_chat_tools_contains_basic_deterministic_tools():
    """函数作用：验证默认聊天工具包含基础确定性工具。
    输入参数：无。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    tool_names = {tool["function"]["name"] for tool in chat_tools.get_chat_tools()}

    assert "get_current_datetime" in tool_names
    assert "calculate_expression" in tool_names
    assert "convert_units" in tool_names
    assert "calendar_info" in tool_names


def test_execute_get_current_datetime_tool():
    """函数作用：验证 get_current_datetime 工具返回指定时区的当前日期时间结构。
    输入参数：无。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    result = asyncio.run(
        chat_tools.execute_chat_tool(
            session=FakeSession(),
            model_client=FakeModelClient(),
            user_id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            tool_name="get_current_datetime",
            arguments={"timezone": "Asia/Shanghai"},
        )
    )

    assert result["timezone"] == "Asia/Shanghai"
    assert result["date"]
    assert result["time"]
    assert result["weekday_zh"].startswith("星期")
    assert result["utc_offset"] == "+08:00"


def test_execute_calculate_expression_tool():
    """函数作用：验证 calculate_expression 工具能安全计算表达式并拒绝危险内容。
    输入参数：无。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    result = asyncio.run(
        chat_tools.execute_chat_tool(
            session=FakeSession(),
            model_client=FakeModelClient(),
            user_id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            tool_name="calculate_expression",
            arguments={"expression": "398 * 17.5%"},
        )
    )
    unsafe_result = asyncio.run(
        chat_tools.execute_chat_tool(
            session=FakeSession(),
            model_client=FakeModelClient(),
            user_id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            tool_name="calculate_expression",
            arguments={"expression": "__import__('os').system('echo bad')"},
        )
    )

    assert result == {"expression": "398 * 17.5%", "result": "69.65"}
    assert "error" in unsafe_result


def test_execute_convert_units_tool():
    """函数作用：验证 convert_units 工具支持常见单位和温度换算。
    输入参数：无。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    length_result = asyncio.run(
        chat_tools.execute_chat_tool(
            session=FakeSession(),
            model_client=FakeModelClient(),
            user_id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            tool_name="convert_units",
            arguments={"value": 100, "from_unit": "厘米", "to_unit": "米"},
        )
    )
    temperature_result = asyncio.run(
        chat_tools.execute_chat_tool(
            session=FakeSession(),
            model_client=FakeModelClient(),
            user_id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            tool_name="convert_units",
            arguments={"value": 0, "from_unit": "摄氏度", "to_unit": "华氏度"},
        )
    )

    assert length_result == {
        "value": "100",
        "from_unit": "cm",
        "to_unit": "m",
        "category": "length",
        "result": "1",
    }
    assert temperature_result["category"] == "temperature"
    assert temperature_result["result"] == "32"


def test_execute_calendar_info_tool():
    """函数作用：验证 calendar_info 工具返回日期信息并支持日期加减。
    输入参数：无。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    info_result = asyncio.run(
        chat_tools.execute_chat_tool(
            session=FakeSession(),
            model_client=FakeModelClient(),
            user_id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            tool_name="calendar_info",
            arguments={"date": "2026-05-19"},
        )
    )
    add_result = asyncio.run(
        chat_tools.execute_chat_tool(
            session=FakeSession(),
            model_client=FakeModelClient(),
            user_id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            tool_name="calendar_info",
            arguments={"date": "2026-05-19", "operation": "add_days", "days_delta": 7},
        )
    )

    assert info_result["date"] == "2026-05-19"
    assert info_result["weekday_zh"] == "星期二"
    assert info_result["is_leap_year"] is False
    assert info_result["days_in_month"] == 31
    assert add_result["date"] == "2026-05-26"


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

        def __init__(self, timeout=None):
            """函数作用：接收生产代码传入的 timeout 参数。
            输入参数：timeout - HTTP 超时配置。
            输出参数：无返回值。
            """
            self.timeout = timeout

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


def test_execute_web_search_tool_returns_timeout_error(monkeypatch):
    """函数作用：验证 SerpApi 超时时返回结构化错误，避免聊天流长时间挂起。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    class TimeoutAsyncClient:
        """类作用：模拟 SerpApi 请求超时。"""

        def __init__(self, timeout=None):
            """函数作用：接收生产代码传入的 timeout 参数。
            输入参数：timeout - HTTP 超时配置。
            输出参数：无返回值。
            """
            self.timeout = timeout

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

        async def get(self, _url, params):
            """函数作用：模拟请求超时。
            输入参数：_url、params - 请求信息。
            输出参数：抛出 TimeoutException。
            """
            raise chat_tools.httpx.TimeoutException("timeout")

    monkeypatch.setattr(chat_tools.httpx, "AsyncClient", TimeoutAsyncClient)
    monkeypatch.setattr(
        chat_tools,
        "get_settings",
        lambda: SimpleNamespace(serpapi_api_key="serp-key", serpapi_timeout_seconds=2.0),
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

    assert result == {
        "error": {
            "code": "WEB_SEARCH_TIMEOUT",
            "message": "SerpApi 在 2 秒内没有响应",
        },
        "instruction": "联网搜索超时。这是内部工具状态，不要向用户提及搜索超时或工具失败；如可回答，基于已有知识作答；如果问题依赖最新外部事实，只说明当前无法核验最新信息。",
    }
