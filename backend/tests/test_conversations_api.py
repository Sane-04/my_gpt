# 模块说明：后端测试模块，验证接口契约、仓储行为和核心服务边界。
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.api import conversations as conversations_api
from app.api.deps import get_current_user
from app.db import get_db
from app.main import app
from app.models.conversation import Conversation
from app.models.enums import MessageRole
from app.models.message import Message
from app.models.user import User


class DummySession:
    """类作用：为 Conversations API 测试提供不连接数据库的占位 Session。"""


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    """函数作用：每个测试前后清理 FastAPI 依赖覆盖。
    输入参数：无。
    输出参数：无返回值。
    """
    app.dependency_overrides.clear()
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


def build_conversation(user_id: uuid.UUID, title: str = "测试会话") -> Conversation:
    """函数作用：构造测试用会话模型。
    输入参数：user_id - 所属用户 UUID；title - 会话标题。
    输出参数：Conversation 模型实例。
    """
    now = datetime(2026, 5, 16, 9, 0, tzinfo=timezone.utc)
    conversation = Conversation(user_id=user_id, title=title)
    conversation.id = uuid.uuid4()
    conversation.created_at = now
    conversation.updated_at = now
    return conversation


def build_message(user_id: uuid.UUID, conversation_id: uuid.UUID, role: MessageRole, content: str) -> Message:
    """函数作用：构造测试用消息模型。
    输入参数：user_id - 所属用户 UUID；conversation_id - 所属会话 UUID；role - 消息角色；content - 消息正文。
    输出参数：Message 模型实例。
    """
    message = Message(user_id=user_id, conversation_id=conversation_id, role=role, content=content)
    message.id = uuid.uuid4()
    message.created_at = datetime(2026, 5, 16, 9, 1, tzinfo=timezone.utc)
    return message


def install_auth_overrides(user: User):
    """函数作用：安装当前用户和数据库依赖覆盖。
    输入参数：user - 当前登录用户。
    输出参数：无返回值。
    """
    async def _helper_get_current_user():
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = _helper_get_current_user


def test_create_conversation_returns_frontend_contract(monkeypatch):
    """函数作用：验证创建会话接口返回前端契约。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    user = build_user()
    install_auth_overrides(user)
    captured_user_id = None

    async def _helper_create_conversation(_session, user_id, title):
        nonlocal captured_user_id
        captured_user_id = user_id
        return build_conversation(user_id=user_id, title=title)

    monkeypatch.setattr(conversations_api, "create_conversation", _helper_create_conversation)

    response = TestClient(app).post("/api/conversations", json={"title": "测试会话"})
    payload = response.json()

    assert response.status_code == 200
    assert captured_user_id == user.id
    assert payload["conversation"]["title"] == "测试会话"
    assert payload["conversation"]["id"]
    assert payload["conversation"]["createdAt"]
    assert payload["conversation"]["updatedAt"]


def test_list_conversations_returns_conversations_key(monkeypatch):
    """函数作用：验证会话列表接口返回 conversations 字段。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    user = build_user()
    install_auth_overrides(user)

    async def _helper_list_conversations(_session, user_id):
        return [build_conversation(user_id=user_id)]

    monkeypatch.setattr(conversations_api, "list_conversations", _helper_list_conversations)

    response = TestClient(app).get("/api/conversations")

    assert response.status_code == 200
    assert len(response.json()["conversations"]) == 1


def test_get_conversation_returns_404_for_missing_or_foreign_conversation(monkeypatch):
    """函数作用：验证会话不存在或不属于当前用户时返回标准 404。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    user = build_user()
    install_auth_overrides(user)

    async def _helper_get_conversation_by_id(_session, _user_id, _conversation_id):
        return None

    monkeypatch.setattr(conversations_api, "get_conversation_by_id", _helper_get_conversation_by_id)

    response = TestClient(app).get(f"/api/conversations/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"error": {"code": "CONVERSATION_NOT_FOUND", "message": "会话不存在"}}


def test_delete_conversation_returns_deleted_id(monkeypatch):
    """函数作用：验证硬删除会话接口返回 deleted_id。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    user = build_user()
    install_auth_overrides(user)
    conversation_id = uuid.uuid4()

    async def _helper_delete_conversation_by_id(_session, user_id, requested_conversation_id):
        return user_id == user.id and requested_conversation_id == conversation_id

    monkeypatch.setattr(conversations_api, "delete_conversation_by_id", _helper_delete_conversation_by_id)

    response = TestClient(app).delete(f"/api/conversations/{conversation_id}")

    assert response.status_code == 200
    assert response.json() == {"deleted_id": str(conversation_id)}


def test_get_messages_returns_frontend_message_contract(monkeypatch):
    """函数作用：验证会话消息接口返回前端消息契约。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    user = build_user()
    conversation = build_conversation(user.id)
    message = build_message(user.id, conversation.id, MessageRole.USER, "你好")
    message.metadata_ = {
        "images": [
            {
                "name": "cat.png",
                "mimeType": "image/png",
                "size": 12,
                "dataUrl": "data:image/png;base64,aGVsbG8=",
            }
        ],
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
    }
    install_auth_overrides(user)

    async def _helper_get_conversation_by_id(_session, _user_id, _conversation_id):
        return conversation

    async def _helper_list_messages_page(_session, _user_id, _conversation_id, limit, before=None):
        assert limit == conversations_api.MESSAGE_PAGE_SIZE
        assert before is None
        return [message], False

    monkeypatch.setattr(conversations_api, "get_conversation_by_id", _helper_get_conversation_by_id)
    monkeypatch.setattr(conversations_api, "list_messages_page", _helper_list_messages_page)

    response = TestClient(app).get(f"/api/conversations/{conversation.id}/messages")
    payload = response.json()

    assert response.status_code == 200
    assert payload["hasMore"] is False
    assert payload["messages"][0]["conversationId"] == str(conversation.id)
    assert payload["messages"][0]["role"] == "user"
    assert payload["messages"][0]["content"] == "你好"
    assert payload["messages"][0]["status"] == "complete"
    assert payload["messages"][0]["images"][0]["name"] == "cat.png"
    assert payload["messages"][0]["sources"][0]["id"] == "src_1"
    assert payload["messages"][0]["citationGroups"][0]["label"] == "OpenAI News"


def test_get_messages_accepts_pagination_query(monkeypatch):
    """函数作用：验证会话消息接口支持 limit 和 before 分页参数。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    user = build_user()
    conversation = build_conversation(user.id)
    message = build_message(user.id, conversation.id, MessageRole.USER, "更早消息")
    before = datetime(2026, 5, 16, 9, 10, tzinfo=timezone.utc)
    captured_limit = None
    captured_before = None
    install_auth_overrides(user)

    async def _helper_get_conversation_by_id(_session, _user_id, _conversation_id):
        return conversation

    async def _helper_list_messages_page(_session, _user_id, _conversation_id, limit, before=None):
        nonlocal captured_limit, captured_before
        captured_limit = limit
        captured_before = before
        return [message], True

    monkeypatch.setattr(conversations_api, "get_conversation_by_id", _helper_get_conversation_by_id)
    monkeypatch.setattr(conversations_api, "list_messages_page", _helper_list_messages_page)

    response = TestClient(app).get(
        f"/api/conversations/{conversation.id}/messages",
        params={"limit": 2, "before": before.isoformat()},
    )
    payload = response.json()

    assert response.status_code == 200
    assert captured_limit == 2
    assert captured_before == before
    assert payload["hasMore"] is True
    assert payload["messages"][0]["content"] == "更早消息"
