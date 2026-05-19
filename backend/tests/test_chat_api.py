# 模块说明：后端测试模块，验证接口契约、仓储行为和核心服务边界。
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.api import chat as chat_api
from app.api.deps import get_current_user
from app.db import get_db
from app.main import app
from app.models.conversation import Conversation
from app.models.enums import EmbeddingStatus, MessageRole
from app.models.long_term_memory import LongTermMemory
from app.models.message import Message
from app.models.user import User
from app.services.model_client import ModelStreamError


class DummySession:
    """类作用：为 Chat API 测试提供不连接数据库的占位 Session。"""


class FakeModelClient:
    """类作用：模拟成功的模型流式客户端。"""

    captured_messages = None
    captured_tools = None

    def __init__(self):
        """函数作用：初始化模拟模型客户端。
        输入参数：无。
        输出参数：无返回值。
        """

    async def create_embedding(self, _text):
        """函数作用：返回固定 embedding。
        输入参数：_text - 待向量化文本。
        输出参数：固定 embedding。
        """
        return [0.1, 0.2, 0.3]

    async def stream_chat_completion(self, _messages, _tools=None):
        """函数作用：返回两段文本 delta 和完成事件。
        输入参数：_messages - 模型输入消息；_tools - 工具定义。
        输出参数：异步产出模型流事件。
        """
        FakeModelClient.captured_messages = _messages
        FakeModelClient.captured_tools = _tools
        yield {"type": "delta", "delta": "你"}
        yield {"type": "delta", "delta": "好"}
        yield {"type": "completed", "content": "你好", "tool_calls": [], "finish_reason": "stop"}


class FakeMultiRoundToolModelClient:
    """类作用：模拟会触发多轮 Chat Completions 工具调用的模型客户端。"""

    captured_messages = None

    def __init__(self):
        """函数作用：初始化模拟模型客户端。
        输入参数：无。
        输出参数：无返回值。
        """
        self.round_count = 0

    async def create_embedding(self, _text):
        """函数作用：返回固定 embedding。
        输入参数：_text - 待向量化文本。
        输出参数：固定 embedding。
        """
        return [0.1, 0.2, 0.3]

    async def stream_chat_completion(self, _messages, _tools=None):
        """函数作用：前两轮返回工具调用，第三轮返回最终文本。
        输入参数：_messages - 模型输入消息；_tools - 工具定义。
        输出参数：异步产出模型流事件。
        """
        self.round_count += 1
        if self.round_count == 1:
            yield {
                "type": "completed",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call-1",
                        "type": "function",
                        "function": {
                            "name": "list_long_term_memory",
                            "arguments": {"limit": 5},
                            "arguments_text": '{"limit": 5}',
                        },
                    }
                ],
                "finish_reason": "tool_calls",
            }
            return

        if self.round_count == 2:
            yield {
                "type": "completed",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call-2",
                        "type": "function",
                        "function": {
                            "name": "save_long_term_memory",
                            "arguments": {
                                "title": "运动兴趣",
                                "memory_key": "sports_basketball_preference",
                                "content": "用户爱打篮球。",
                            },
                            "arguments_text": '{"title": "运动兴趣", "memory_key": "sports_basketball_preference", "content": "用户爱打篮球。"}',
                        },
                    }
                ],
                "finish_reason": "tool_calls",
            }
            return

        FakeMultiRoundToolModelClient.captured_messages = _messages
        yield {"type": "delta", "delta": "已保存"}
        yield {"type": "completed", "content": "已保存", "tool_calls": [], "finish_reason": "stop"}


class FakeWebSearchToolModelClient:
    """类作用：模拟会调用联网搜索工具并返回引用标记的模型客户端。"""

    def __init__(self):
        """函数作用：初始化模拟模型客户端。
        输入参数：无。
        输出参数：无返回值。
        """
        self.round_count = 0

    async def create_embedding(self, _text):
        """函数作用：返回固定 embedding。
        输入参数：_text - 待向量化文本。
        输出参数：固定 embedding。
        """
        return [0.1, 0.2, 0.3]

    async def stream_chat_completion(self, _messages, _tools=None):
        """函数作用：第一轮请求联网搜索，第二轮返回带 citation 标记的文本。
        输入参数：_messages - 模型输入消息；_tools - 工具定义。
        输出参数：异步产出模型流事件。
        """
        self.round_count += 1
        if self.round_count == 1:
            yield {
                "type": "completed",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call-web",
                        "type": "function",
                        "function": {
                            "name": "web_search",
                            "arguments": {"query": "OpenAI 最新消息", "limit": 2},
                            "arguments_text": '{"query": "OpenAI 最新消息", "limit": 2}',
                        },
                    }
                ],
                "finish_reason": "tool_calls",
            }
            return

        yield {"type": "delta", "delta": "1. 最新动态来自搜索结果。[[cite:src_1]]"}
        yield {
            "type": "completed",
            "content": "1. 最新动态来自搜索结果。[[cite:src_1]]",
            "tool_calls": [],
            "finish_reason": "stop",
        }


class FailingModelClient:
    """类作用：模拟失败的模型流式客户端。"""

    def __init__(self):
        """函数作用：初始化模拟模型客户端。
        输入参数：无。
        输出参数：无返回值。
        """

    async def create_embedding(self, _text):
        """函数作用：返回固定 embedding。
        输入参数：_text - 待向量化文本。
        输出参数：固定 embedding。
        """
        return [0.1, 0.2, 0.3]

    async def stream_chat_completion(self, _messages, _tools=None):
        """函数作用：抛出模型流错误。
        输入参数：_messages - 模型输入消息；_tools - 工具定义。
        输出参数：异步生成器。
        """
        if False:
            yield {}
        raise ModelStreamError("模型失败")


class EmbeddingFailingModelClient(FakeModelClient):
    """类作用：模拟 embedding 失败但模型流成功的客户端。"""

    async def create_embedding(self, _text):
        """函数作用：模拟 embedding 生成失败。
        输入参数：_text - 待向量化文本。
        输出参数：抛出异常。
        """
        raise RuntimeError("embedding 失败")


@pytest.fixture(autouse=True)
def clear_dependency_overrides(monkeypatch):
    """函数作用：每个测试前后清理 FastAPI 依赖覆盖。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值。
    """
    async def _helper_list_long_term_memories(_session, _user_id):
        return []

    app.dependency_overrides.clear()
    monkeypatch.setattr(chat_api, "list_long_term_memories", _helper_list_long_term_memories)
    yield
    app.dependency_overrides.clear()


async def override_get_db():
    """函数作用：覆盖真实数据库依赖，避免接口测试连接 PostgreSQL。
    输入参数：无。
    输出参数：异步生成 DummySession。
    """
    yield DummySession()


def build_user() -> User:
    """函数作用：构造当前登录用户。
    输入参数：无。
    输出参数：User 模型实例。
    """
    user = User(email="tester@example.com", display_name="Tester", password_hash="hashed")
    user.id = uuid.uuid4()
    user.is_active = True
    return user


def build_conversation(user_id: uuid.UUID) -> Conversation:
    """函数作用：构造测试用会话模型。
    输入参数：user_id - 所属用户 UUID。
    输出参数：Conversation 模型实例。
    """
    now = datetime(2026, 5, 16, 9, 0, tzinfo=timezone.utc)
    conversation = Conversation(user_id=user_id, title="新的对话")
    conversation.id = uuid.uuid4()
    conversation.created_at = now
    conversation.updated_at = now
    return conversation


def build_message(user_id: uuid.UUID, conversation_id: uuid.UUID, role: MessageRole, content: str) -> Message:
    """函数作用：构造测试用消息模型。
    输入参数：user_id - 所属用户 UUID；conversation_id - 会话 UUID；role - 消息角色；content - 消息正文。
    输出参数：Message 模型实例。
    """
    message = Message(user_id=user_id, conversation_id=conversation_id, role=role, content=content)
    message.id = uuid.uuid4()
    message.created_at = datetime(2026, 5, 16, 9, 1, tzinfo=timezone.utc)
    return message


def build_message_at(
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    role: MessageRole,
    content: str,
    minute: int,
) -> Message:
    """函数作用：构造指定创建时间的消息模型。
    输入参数：user_id - 所属用户 UUID；conversation_id - 会话 UUID；role - 消息角色；content - 消息正文；minute - 分钟。
    输出参数：Message 模型实例。
    """
    message = build_message(user_id, conversation_id, role, content)
    message.created_at = datetime(2026, 5, 16, 9, minute, tzinfo=timezone.utc)
    return message


def build_memory(user_id: uuid.UUID, title: str, memory_key: str, content: str) -> LongTermMemory:
    """函数作用：构造长期记忆模型。
    输入参数：user_id - 所属用户 UUID；title - 标题；memory_key - 记忆键；content - 正文。
    输出参数：LongTermMemory 模型实例。
    """
    memory = LongTermMemory(
        user_id=user_id,
        content=content,
        metadata_={"title": title, "memory_key": memory_key, "source": "manual"},
    )
    memory.id = uuid.uuid4()
    memory.created_at = datetime(2026, 5, 16, 9, 1, tzinfo=timezone.utc)
    memory.updated_at = datetime(2026, 5, 16, 9, 1, tzinfo=timezone.utc)
    return memory


def install_auth_overrides(user: User):
    """函数作用：安装当前用户和数据库依赖覆盖。
    输入参数：user - 当前登录用户。
    输出参数：无返回值。
    """
    async def _helper_get_current_user():
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = _helper_get_current_user


def test_chat_stream_requires_owned_conversation(monkeypatch):
    """函数作用：验证非本人或不存在会话返回 404。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    user = build_user()
    install_auth_overrides(user)

    async def _helper_get_conversation_by_id(_session, _user_id, _conversation_id):
        return None

    monkeypatch.setattr(chat_api, "get_conversation_by_id", _helper_get_conversation_by_id)

    response = TestClient(app).post(
        "/api/chat/stream",
        json={"conversationId": str(uuid.uuid4()), "content": "你好"},
    )

    assert response.status_code == 404
    assert response.json() == {"error": {"code": "CONVERSATION_NOT_FOUND", "message": "会话不存在"}}


def test_chat_stream_returns_delta_done_and_saves_messages(monkeypatch):
    """函数作用：验证聊天流返回 delta/done 并保存用户和助手消息。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    user = build_user()
    conversation = build_conversation(user.id)
    saved_messages = []
    updated_titles = []
    install_auth_overrides(user)

    async def _helper_get_conversation_by_id(_session, _user_id, _conversation_id):
        return conversation

    async def _helper_count_messages(_session, _user_id, _conversation_id):
        return 0

    async def _helper_create_message(_session, user_id, conversation_id, role, content, metadata=None):
        message = build_message(user_id, conversation_id, role, content)
        saved_messages.append((role, content, metadata))
        return message

    async def _helper_update_conversation_title(_session, _user_id, _conversation_id, title):
        updated_titles.append(title)
        return conversation

    async def _helper_list_recent_messages(_session, _user_id, _conversation_id, _limit):
        return [saved_messages[-1][3]] if len(saved_messages[-1]) > 3 else []

    async def _helper_update_message_embedding_result(_session, message_id, _user_id, embedding, status, error):
        return None

    monkeypatch.setattr(chat_api, "get_conversation_by_id", _helper_get_conversation_by_id)
    monkeypatch.setattr(chat_api, "count_messages", _helper_count_messages)
    async def _helper_create_message_with_object(_session, user_id, conversation_id, role, content, metadata=None):
        message = build_message(user_id, conversation_id, role, content)
        saved_messages.append((role, content, metadata, message))
        return message

    monkeypatch.setattr(chat_api, "create_message", _helper_create_message_with_object)
    monkeypatch.setattr(chat_api, "list_recent_messages", _helper_list_recent_messages)
    monkeypatch.setattr(chat_api, "update_message_embedding_result", _helper_update_message_embedding_result)
    monkeypatch.setattr(chat_api, "update_conversation_title", _helper_update_conversation_title)
    monkeypatch.setattr(chat_api, "ChatCompletionsModelClient", FakeModelClient)

    response = TestClient(app).post(
        "/api/chat/stream",
        json={"conversationId": str(conversation.id), "content": "  你好  "},
    )

    assert response.status_code == 200
    assert response.text.splitlines() == [
        '{"type": "delta", "delta": "你"}',
        '{"type": "delta", "delta": "好"}',
        '{"type": "done"}',
    ]
    assert saved_messages[0][:3] == (MessageRole.USER, "你好", None)
    assert saved_messages[1][:3] == (MessageRole.ASSISTANT, "你好", None)
    assert updated_titles == ["你好"]
    assert "web_search" not in [tool["function"]["name"] for tool in FakeModelClient.captured_tools]


def test_chat_stream_exposes_web_search_tool_when_enabled(monkeypatch):
    """函数作用：验证开启联网搜索时聊天流会把 web_search 工具暴露给模型。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    user = build_user()
    conversation = build_conversation(user.id)
    install_auth_overrides(user)

    async def _helper_get_conversation_by_id(_session, _user_id, _conversation_id):
        return conversation

    async def _helper_count_messages(_session, _user_id, _conversation_id):
        return 1

    async def _helper_create_message(_session, user_id, conversation_id, role, content, metadata=None):
        return build_message(user_id, conversation_id, role, content)

    async def _helper_list_recent_messages(_session, _user_id, _conversation_id, _limit):
        return []

    async def _helper_update_message_embedding_result(_session, _message_id, _user_id, _embedding, _status, _error):
        return None

    monkeypatch.setattr(chat_api, "get_conversation_by_id", _helper_get_conversation_by_id)
    monkeypatch.setattr(chat_api, "count_messages", _helper_count_messages)
    monkeypatch.setattr(chat_api, "create_message", _helper_create_message)
    monkeypatch.setattr(chat_api, "list_recent_messages", _helper_list_recent_messages)
    monkeypatch.setattr(chat_api, "update_message_embedding_result", _helper_update_message_embedding_result)
    monkeypatch.setattr(chat_api, "ChatCompletionsModelClient", FakeModelClient)

    response = TestClient(app).post(
        "/api/chat/stream",
        json={"conversationId": str(conversation.id), "content": "查一下最新消息", "enableWebSearch": True},
    )

    assert response.status_code == 200
    assert "web_search" in [tool["function"]["name"] for tool in FakeModelClient.captured_tools]


def test_chat_stream_sends_images_as_multimodal_content(monkeypatch):
    """函数作用：验证聊天图片会保存到消息 metadata，并以多模态 content parts 传给模型。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    user = build_user()
    conversation = build_conversation(user.id)
    saved_messages = []
    image = {
        "name": "cat.png",
        "mimeType": "image/png",
        "size": 12,
        "dataUrl": "data:image/png;base64,aGVsbG8=",
    }
    install_auth_overrides(user)

    async def _helper_get_conversation_by_id(_session, _user_id, _conversation_id):
        return conversation

    async def _helper_count_messages(_session, _user_id, _conversation_id):
        return 1

    async def _helper_create_message(_session, user_id, conversation_id, role, content, metadata=None):
        message = build_message(user_id, conversation_id, role, content)
        saved_messages.append((role, content, metadata))
        return message

    async def _helper_list_recent_messages(_session, _user_id, _conversation_id, _limit):
        return []

    async def _helper_update_message_embedding_result(_session, _message_id, _user_id, _embedding, _status, _error):
        return None

    monkeypatch.setattr(chat_api, "get_conversation_by_id", _helper_get_conversation_by_id)
    monkeypatch.setattr(chat_api, "count_messages", _helper_count_messages)
    monkeypatch.setattr(chat_api, "create_message", _helper_create_message)
    monkeypatch.setattr(chat_api, "list_recent_messages", _helper_list_recent_messages)
    monkeypatch.setattr(chat_api, "update_message_embedding_result", _helper_update_message_embedding_result)
    monkeypatch.setattr(chat_api, "ChatCompletionsModelClient", FakeModelClient)

    response = TestClient(app).post(
        "/api/chat/stream",
        json={"conversationId": str(conversation.id), "content": "看看这张图", "images": [image]},
    )

    assert response.status_code == 200
    assert saved_messages[0] == (MessageRole.USER, "看看这张图", {"images": [image]})
    assert FakeModelClient.captured_messages[-1] == {
        "role": "user",
        "content": [
            {"type": "text", "text": "看看这张图"},
            {"type": "image_url", "image_url": {"url": image["dataUrl"]}},
        ],
    }


def test_chat_stream_saves_web_search_sources_metadata(monkeypatch):
    """函数作用：验证联网搜索来源会写入助手消息 metadata 并通过流事件返回。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    user = build_user()
    conversation = build_conversation(user.id)
    saved_messages = []
    install_auth_overrides(user)

    async def _helper_get_conversation_by_id(_session, _user_id, _conversation_id):
        return conversation

    async def _helper_count_messages(_session, _user_id, _conversation_id):
        return 1

    async def _helper_create_message(_session, user_id, conversation_id, role, content, metadata=None):
        message = build_message(user_id, conversation_id, role, content)
        saved_messages.append((role, content, metadata))
        return message

    async def _helper_list_recent_messages(_session, _user_id, _conversation_id, _limit):
        return []

    async def _helper_update_message_embedding_result(_session, _message_id, _user_id, _embedding, _status, _error):
        return None

    async def _helper_create_tool_call_event(_session, _user_id, _conversation_id, _tool_name, _arguments):
        return type("ToolEvent", (), {"id": uuid.uuid4()})()

    async def _helper_mark_tool_call_succeeded(_session, event, _result):
        return event

    async def _helper_execute_chat_tool(**_kwargs):
        return {
            "query": "OpenAI 最新消息",
            "results": [
                {
                    "id": "src_1",
                    "title": "OpenAI News",
                    "url": "https://example.com/openai-news",
                    "domain": "example.com",
                    "snippet": "模型新闻摘要",
                    "source": "web",
                }
            ],
        }

    monkeypatch.setattr(chat_api, "get_conversation_by_id", _helper_get_conversation_by_id)
    monkeypatch.setattr(chat_api, "count_messages", _helper_count_messages)
    monkeypatch.setattr(chat_api, "create_message", _helper_create_message)
    monkeypatch.setattr(chat_api, "list_recent_messages", _helper_list_recent_messages)
    monkeypatch.setattr(chat_api, "update_message_embedding_result", _helper_update_message_embedding_result)
    monkeypatch.setattr(chat_api, "create_tool_call_event", _helper_create_tool_call_event)
    monkeypatch.setattr(chat_api, "mark_tool_call_succeeded", _helper_mark_tool_call_succeeded)
    monkeypatch.setattr(chat_api, "execute_chat_tool", _helper_execute_chat_tool)
    monkeypatch.setattr(chat_api, "ChatCompletionsModelClient", FakeWebSearchToolModelClient)

    response = TestClient(app).post(
        "/api/chat/stream",
        json={"conversationId": str(conversation.id), "content": "查一下最新消息", "enableWebSearch": True},
    )

    assert response.status_code == 200
    assert response.text.splitlines() == [
        '{"type": "tool_call_started", "toolName": "web_search"}',
        '{"type": "tool_call_finished", "toolName": "web_search"}',
        '{"type": "delta", "delta": "1. 最新动态来自搜索结果。[[cite:src_1]]"}',
        '{"type": "sources", "sources": [{"id": "src_1", "title": "OpenAI News", "url": "https://example.com/openai-news", "domain": "example.com", "snippet": "模型新闻摘要", "source": "web"}], "citationGroups": [{"id": "cite_1", "label": "OpenAI News", "sourceIds": ["src_1"]}]}',
        '{"type": "done"}',
    ]
    assert saved_messages[-1] == (
        MessageRole.ASSISTANT,
        "1. 最新动态来自搜索结果。[[cite:src_1]]",
        {
            "sources": [
                {
                    "id": "src_1",
                    "title": "OpenAI News",
                    "url": "https://example.com/openai-news",
                    "domain": "example.com",
                    "snippet": "模型新闻摘要",
                    "source": "web",
                }
            ],
            "citationGroups": [{"id": "cite_1", "label": "OpenAI News", "sourceIds": ["src_1"]}],
        },
    )


def test_chat_stream_returns_error_event_and_does_not_save_empty_assistant(monkeypatch):
    """函数作用：验证模型失败时返回 error 事件且不保存空助手消息。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    user = build_user()
    conversation = build_conversation(user.id)
    saved_messages = []
    install_auth_overrides(user)

    async def _helper_get_conversation_by_id(_session, _user_id, _conversation_id):
        return conversation

    async def _helper_count_messages(_session, _user_id, _conversation_id):
        return 1

    async def _helper_create_message(_session, user_id, conversation_id, role, content, metadata=None):
        message = build_message(user_id, conversation_id, role, content)
        saved_messages.append((role, content, metadata))
        return message

    async def _helper_list_recent_messages(_session, _user_id, _conversation_id, _limit):
        return []

    async def _helper_update_message_embedding_result(_session, _message_id, _user_id, _embedding, _status, _error):
        return None

    monkeypatch.setattr(chat_api, "get_conversation_by_id", _helper_get_conversation_by_id)
    monkeypatch.setattr(chat_api, "count_messages", _helper_count_messages)
    monkeypatch.setattr(chat_api, "create_message", _helper_create_message)
    monkeypatch.setattr(chat_api, "list_recent_messages", _helper_list_recent_messages)
    monkeypatch.setattr(chat_api, "update_message_embedding_result", _helper_update_message_embedding_result)
    monkeypatch.setattr(chat_api, "ChatCompletionsModelClient", FailingModelClient)

    response = TestClient(app).post(
        "/api/chat/stream",
        json={"conversationId": str(conversation.id), "content": "你好"},
    )

    assert response.status_code == 200
    assert response.text.splitlines() == ['{"type": "error", "message": "模型失败"}']
    assert saved_messages == [(MessageRole.USER, "你好", None)]


def test_chat_stream_sanitizes_upstream_html_gateway_error(monkeypatch):
    """函数作用：验证上游模型网关返回 HTML 502 时，聊天流返回可读中文错误。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    class HtmlGatewayFailingModelClient(FailingModelClient):
        """类作用：模拟模型服务返回 nginx HTML 502。"""

        async def stream_chat_completion(self, _messages, _tools=None):
            """函数作用：抛出包含 HTML 的模型流错误。
            输入参数：_messages - 模型输入消息；_tools - 工具定义。
            输出参数：异步生成器。
            """
            if False:
                yield {}
            raise ModelStreamError(
                "<html> <head><title>502 Bad Gateway</title></head> "
                "<body> <center><h1>502 Bad Gateway</h1></center> "
                "<hr><center>nginx/1.22.1</center> </body> </html>"
            )

    user = build_user()
    conversation = build_conversation(user.id)
    install_auth_overrides(user)

    async def _helper_get_conversation_by_id(_session, _user_id, _conversation_id):
        return conversation

    async def _helper_count_messages(_session, _user_id, _conversation_id):
        return 1

    async def _helper_create_message(_session, user_id, conversation_id, role, content, metadata=None):
        return build_message(user_id, conversation_id, role, content)

    async def _helper_list_recent_messages(_session, _user_id, _conversation_id, _limit):
        return []

    async def _helper_update_message_embedding_result(_session, _message_id, _user_id, _embedding, _status, _error):
        return None

    monkeypatch.setattr(chat_api, "get_conversation_by_id", _helper_get_conversation_by_id)
    monkeypatch.setattr(chat_api, "count_messages", _helper_count_messages)
    monkeypatch.setattr(chat_api, "create_message", _helper_create_message)
    monkeypatch.setattr(chat_api, "list_recent_messages", _helper_list_recent_messages)
    monkeypatch.setattr(chat_api, "update_message_embedding_result", _helper_update_message_embedding_result)
    monkeypatch.setattr(chat_api, "ChatCompletionsModelClient", HtmlGatewayFailingModelClient)

    response = TestClient(app).post(
        "/api/chat/stream",
        json={"conversationId": str(conversation.id), "content": "联网查一下", "enableWebSearch": True},
    )

    assert response.status_code == 200
    assert response.text.splitlines() == [
        '{"type": "error", "message": "模型服务网关错误（502 Bad Gateway），请检查 OPENAI_BASE_URL 对应服务是否可用，或稍后重试"}'
    ]


def test_prompt_snapshot_saved_only_when_enabled(monkeypatch):
    """函数作用：验证配置开启时才保存 Prompt 快照。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    user = build_user()
    conversation = build_conversation(user.id)
    snapshots = []
    install_auth_overrides(user)

    async def _helper_get_conversation_by_id(_session, _user_id, _conversation_id):
        return conversation

    async def _helper_count_messages(_session, _user_id, _conversation_id):
        return 1

    async def _helper_create_message(_session, user_id, conversation_id, role, content, metadata=None):
        return build_message(user_id, conversation_id, role, content)

    async def _helper_list_recent_messages(_session, _user_id, _conversation_id, _limit):
        return [build_message(user.id, conversation.id, MessageRole.ASSISTANT, "历史回复")]

    async def _helper_update_message_embedding_result(_session, _message_id, _user_id, _embedding, _status, _error):
        return None

    async def _helper_create_prompt_snapshot(**kwargs):
        snapshots.append(kwargs)

    monkeypatch.setattr(chat_api, "get_conversation_by_id", _helper_get_conversation_by_id)
    monkeypatch.setattr(chat_api, "count_messages", _helper_count_messages)
    monkeypatch.setattr(chat_api, "create_message", _helper_create_message)
    monkeypatch.setattr(chat_api, "list_recent_messages", _helper_list_recent_messages)
    monkeypatch.setattr(chat_api, "update_message_embedding_result", _helper_update_message_embedding_result)
    monkeypatch.setattr(chat_api, "ChatCompletionsModelClient", FakeModelClient)
    monkeypatch.setattr(chat_api, "create_prompt_snapshot", _helper_create_prompt_snapshot)
    monkeypatch.setattr(
        chat_api,
        "get_settings",
        lambda: type(
            "Settings",
            (),
            {"save_prompt_snapshots": True, "chat_model": "test-model", "context_window_size": 5},
        )(),
    )

    response = TestClient(app).post(
        "/api/chat/stream",
        json={"conversationId": str(conversation.id), "content": "你好"},
    )

    assert response.status_code == 200
    assert len(snapshots) == 1
    assert snapshots[0]["model"] == "test-model"
    assert snapshots[0]["prompt"] == "你好"
    assert snapshots[0]["messages"][-2:] == [
        {"role": "assistant", "content": "历史回复"},
        {"role": "user", "content": "你好"},
    ]
    assert snapshots[0]["messages"][0]["role"] == "system"
    assert snapshots[0]["messages"][1]["role"] == "system"


def test_chat_stream_sends_recent_context_window_to_model(monkeypatch):
    """函数作用：验证模型请求携带最近 5 条上下文消息和当前用户消息。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    user = build_user()
    conversation = build_conversation(user.id)
    user_message = build_message_at(user.id, conversation.id, MessageRole.USER, "当前问题", 10)
    history_messages = [
        build_message_at(user.id, conversation.id, MessageRole.USER, "历史1", 1),
        build_message_at(user.id, conversation.id, MessageRole.ASSISTANT, "历史2", 2),
        build_message_at(user.id, conversation.id, MessageRole.USER, "历史3", 3),
        build_message_at(user.id, conversation.id, MessageRole.ASSISTANT, "历史4", 4),
        build_message_at(user.id, conversation.id, MessageRole.USER, "历史5", 5),
        user_message,
    ]
    install_auth_overrides(user)

    async def _helper_get_conversation_by_id(_session, _user_id, _conversation_id):
        return conversation

    async def _helper_count_messages(_session, _user_id, _conversation_id):
        return 5

    async def _helper_create_message(_session, user_id, conversation_id, role, content, metadata=None):
        if role == MessageRole.USER:
            return user_message
        return build_message(user_id, conversation_id, role, content)

    async def _helper_list_recent_messages(_session, _user_id, _conversation_id, limit):
        assert limit == 6
        return history_messages

    async def _helper_update_message_embedding_result(_session, _message_id, _user_id, _embedding, _status, _error):
        return None

    monkeypatch.setattr(chat_api, "get_conversation_by_id", _helper_get_conversation_by_id)
    monkeypatch.setattr(chat_api, "count_messages", _helper_count_messages)
    monkeypatch.setattr(chat_api, "create_message", _helper_create_message)
    monkeypatch.setattr(chat_api, "list_recent_messages", _helper_list_recent_messages)
    monkeypatch.setattr(chat_api, "update_message_embedding_result", _helper_update_message_embedding_result)
    monkeypatch.setattr(chat_api, "ChatCompletionsModelClient", FakeModelClient)
    monkeypatch.setattr(
        chat_api,
        "get_settings",
        lambda: type(
            "Settings",
            (),
            {"save_prompt_snapshots": False, "chat_model": "test-model", "context_window_size": 5},
        )(),
    )

    response = TestClient(app).post(
        "/api/chat/stream",
        json={"conversationId": str(conversation.id), "content": "当前问题"},
    )

    assert response.status_code == 200
    assert FakeModelClient.captured_messages[-6:] == [
        {"role": "user", "content": "历史1"},
        {"role": "assistant", "content": "历史2"},
        {"role": "user", "content": "历史3"},
        {"role": "assistant", "content": "历史4"},
        {"role": "user", "content": "历史5"},
        {"role": "user", "content": "当前问题"},
    ]
    assert FakeModelClient.captured_messages[0]["role"] == "system"
    assert FakeModelClient.captured_messages[1]["role"] == "system"


def test_chat_stream_injects_long_term_memory(monkeypatch):
    """函数作用：验证聊天请求会注入当前用户长期记忆。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    user = build_user()
    conversation = build_conversation(user.id)
    install_auth_overrides(user)

    async def _helper_get_conversation_by_id(_session, _user_id, _conversation_id):
        return conversation

    async def _helper_count_messages(_session, _user_id, _conversation_id):
        return 1

    async def _helper_create_message(_session, user_id, conversation_id, role, content, metadata=None):
        return build_message(user_id, conversation_id, role, content)

    async def _helper_list_recent_messages(_session, _user_id, _conversation_id, _limit):
        return []

    async def _helper_update_message_embedding_result(_session, _message_id, _user_id, _embedding, _status, _error):
        return None

    async def _helper_list_long_term_memories(_session, _user_id):
        return [build_memory(user.id, "沟通偏好", "communication", "用户喜欢简洁回答")]

    monkeypatch.setattr(chat_api, "get_conversation_by_id", _helper_get_conversation_by_id)
    monkeypatch.setattr(chat_api, "count_messages", _helper_count_messages)
    monkeypatch.setattr(chat_api, "create_message", _helper_create_message)
    monkeypatch.setattr(chat_api, "list_recent_messages", _helper_list_recent_messages)
    monkeypatch.setattr(chat_api, "update_message_embedding_result", _helper_update_message_embedding_result)
    monkeypatch.setattr(chat_api, "list_long_term_memories", _helper_list_long_term_memories)
    monkeypatch.setattr(chat_api, "ChatCompletionsModelClient", FakeModelClient)

    response = TestClient(app).post(
        "/api/chat/stream",
        json={"conversationId": str(conversation.id), "content": "你好"},
    )

    assert response.status_code == 200
    assert "用户喜欢简洁回答" in FakeModelClient.captured_messages[1]["content"]


def test_chat_stream_truncates_long_term_memory(monkeypatch):
    """函数作用：验证长期记忆注入会按配置字符数截断。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    user = build_user()
    conversation = build_conversation(user.id)
    install_auth_overrides(user)

    async def _helper_get_conversation_by_id(_session, _user_id, _conversation_id):
        return conversation

    async def _helper_count_messages(_session, _user_id, _conversation_id):
        return 1

    async def _helper_create_message(_session, user_id, conversation_id, role, content, metadata=None):
        return build_message(user_id, conversation_id, role, content)

    async def _helper_list_recent_messages(_session, _user_id, _conversation_id, _limit):
        return []

    async def _helper_update_message_embedding_result(_session, _message_id, _user_id, _embedding, _status, _error):
        return None

    async def _helper_list_long_term_memories(_session, _user_id):
        return [build_memory(user.id, "很长", "long", "abcdefg")]

    monkeypatch.setattr(chat_api, "get_conversation_by_id", _helper_get_conversation_by_id)
    monkeypatch.setattr(chat_api, "count_messages", _helper_count_messages)
    monkeypatch.setattr(chat_api, "create_message", _helper_create_message)
    monkeypatch.setattr(chat_api, "list_recent_messages", _helper_list_recent_messages)
    monkeypatch.setattr(chat_api, "update_message_embedding_result", _helper_update_message_embedding_result)
    monkeypatch.setattr(chat_api, "list_long_term_memories", _helper_list_long_term_memories)
    monkeypatch.setattr(chat_api, "ChatCompletionsModelClient", FakeModelClient)
    monkeypatch.setattr(
        chat_api,
        "get_settings",
        lambda: type(
            "Settings",
            (),
            {"save_prompt_snapshots": False, "chat_model": "test-model", "context_window_size": 5, "long_term_memory_max_chars": 8},
        )(),
    )

    response = TestClient(app).post(
        "/api/chat/stream",
        json={"conversationId": str(conversation.id), "content": "你好"},
    )

    assert response.status_code == 200
    assert "已按字符上限截断" in FakeModelClient.captured_messages[1]["content"]


def test_chat_stream_applies_multi_round_chat_tools(monkeypatch):
    """函数作用：验证聊天流会多轮执行模型请求的工具并回灌工具结果。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    user = build_user()
    conversation = build_conversation(user.id)
    tool_events = []
    tool_arguments = []
    install_auth_overrides(user)

    async def _helper_get_conversation_by_id(_session, _user_id, _conversation_id):
        return conversation

    async def _helper_count_messages(_session, _user_id, _conversation_id):
        return 1

    async def _helper_create_message(_session, user_id, conversation_id, role, content, metadata=None):
        return build_message(user_id, conversation_id, role, content)

    async def _helper_list_recent_messages(_session, _user_id, _conversation_id, _limit):
        return []

    async def _helper_update_message_embedding_result(_session, _message_id, _user_id, _embedding, _status, _error):
        return None

    async def _helper_create_tool_call_event(_session, _user_id, _conversation_id, tool_name, arguments):
        event = type("ToolEvent", (), {"id": uuid.uuid4()})()
        tool_events.append((tool_name, arguments))
        return event

    async def _helper_mark_tool_call_succeeded(_session, event, result):
        return event

    async def _helper_execute_chat_tool(**kwargs):
        tool_arguments.append(kwargs["arguments"])
        if kwargs["tool_name"] == "list_long_term_memory":
            return {"memories": []}

        return {"memory": {"id": "memory-1", "content": "用户爱打篮球。"}}

    monkeypatch.setattr(chat_api, "get_conversation_by_id", _helper_get_conversation_by_id)
    monkeypatch.setattr(chat_api, "count_messages", _helper_count_messages)
    monkeypatch.setattr(chat_api, "create_message", _helper_create_message)
    monkeypatch.setattr(chat_api, "list_recent_messages", _helper_list_recent_messages)
    monkeypatch.setattr(chat_api, "update_message_embedding_result", _helper_update_message_embedding_result)
    monkeypatch.setattr(chat_api, "create_tool_call_event", _helper_create_tool_call_event)
    monkeypatch.setattr(chat_api, "mark_tool_call_succeeded", _helper_mark_tool_call_succeeded)
    monkeypatch.setattr(chat_api, "execute_chat_tool", _helper_execute_chat_tool)
    monkeypatch.setattr(chat_api, "ChatCompletionsModelClient", FakeMultiRoundToolModelClient)

    response = TestClient(app).post(
        "/api/chat/stream",
        json={"conversationId": str(conversation.id), "content": "记住我爱打篮球"},
    )

    assert response.status_code == 200
    assert response.text.splitlines() == [
        '{"type": "tool_call_started", "toolName": "list_long_term_memory"}',
        '{"type": "tool_call_finished", "toolName": "list_long_term_memory"}',
        '{"type": "tool_call_started", "toolName": "save_long_term_memory"}',
        '{"type": "tool_call_finished", "toolName": "save_long_term_memory"}',
        '{"type": "delta", "delta": "已保存"}',
        '{"type": "done"}',
    ]
    assert tool_events == [
        (
            "list_long_term_memory",
            {
                "limit": 5,
            },
        ),
        (
            "save_long_term_memory",
            {
                "title": "运动兴趣",
                "memory_key": "sports_basketball_preference",
                "content": "用户爱打篮球。",
            },
        )
    ]
    assert tool_arguments == [
        {
            "limit": 5,
        },
        {
            "title": "运动兴趣",
            "memory_key": "sports_basketball_preference",
            "content": "用户爱打篮球。",
        }
    ]
    assert FakeMultiRoundToolModelClient.captured_messages[-4:] == [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call-1",
                    "type": "function",
                    "function": {"name": "list_long_term_memory", "arguments": '{"limit": 5}'},
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call-1",
            "content": '{"memories": []}',
        },
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call-2",
                    "type": "function",
                    "function": {
                        "name": "save_long_term_memory",
                        "arguments": '{"title": "运动兴趣", "memory_key": "sports_basketball_preference", "content": "用户爱打篮球。"}',
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call-2",
            "content": '{"memory": {"id": "memory-1", "content": "用户爱打篮球。"}}',
        },
    ]


def test_chat_stream_embedding_failure_does_not_block(monkeypatch):
    """函数作用：验证 embedding 失败不会阻塞聊天流完成。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    user = build_user()
    conversation = build_conversation(user.id)
    embedding_updates = []
    install_auth_overrides(user)

    async def _helper_get_conversation_by_id(_session, _user_id, _conversation_id):
        return conversation

    async def _helper_count_messages(_session, _user_id, _conversation_id):
        return 1

    async def _helper_create_message(_session, user_id, conversation_id, role, content, metadata=None):
        return build_message(user_id, conversation_id, role, content)

    async def _helper_list_recent_messages(_session, _user_id, _conversation_id, _limit):
        return []

    async def _helper_update_message_embedding_result(_session, _message_id, _user_id, embedding, status, error):
        embedding_updates.append((embedding, status, error))
        return None

    monkeypatch.setattr(chat_api, "get_conversation_by_id", _helper_get_conversation_by_id)
    monkeypatch.setattr(chat_api, "count_messages", _helper_count_messages)
    monkeypatch.setattr(chat_api, "create_message", _helper_create_message)
    monkeypatch.setattr(chat_api, "list_recent_messages", _helper_list_recent_messages)
    monkeypatch.setattr(chat_api, "update_message_embedding_result", _helper_update_message_embedding_result)
    monkeypatch.setattr(chat_api, "ChatCompletionsModelClient", EmbeddingFailingModelClient)

    response = TestClient(app).post(
        "/api/chat/stream",
        json={"conversationId": str(conversation.id), "content": "你好"},
    )

    assert response.status_code == 200
    assert response.text.splitlines() == [
        '{"type": "delta", "delta": "你"}',
        '{"type": "delta", "delta": "好"}',
        '{"type": "done"}',
    ]
    assert embedding_updates
    assert all(update[1] == EmbeddingStatus.FAILED for update in embedding_updates)
