# 模块说明：后端测试模块，验证接口契约、仓储行为和核心服务边界。
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.api import memories as memories_api
from app.api.deps import get_current_user
from app.db import get_db
from app.main import app
from app.models.long_term_memory import LongTermMemory
from app.models.user import User


class DummySession:
    """类作用：为长期记忆 API 测试提供占位 Session。"""


@pytest.fixture(autouse=True)
def clear_dependency_overrides(monkeypatch):
    """函数作用：每个测试前后清理依赖覆盖并关闭 Markdown 实际写入。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值。
    """
    async def _helper_sync_user_memory_markdown(_session, _user_id):
        return None

    async def _helper_create_memory_event(*_args, **_kwargs):
        return None

    app.dependency_overrides.clear()
    monkeypatch.setattr(memories_api, "_sync_user_memory_markdown", _helper_sync_user_memory_markdown)
    monkeypatch.setattr(memories_api, "create_memory_event", _helper_create_memory_event)
    yield
    app.dependency_overrides.clear()


async def override_get_db():
    """函数作用：覆盖真实数据库依赖。
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


def build_memory(user_id: uuid.UUID, content: str = "用户喜欢简洁回答") -> LongTermMemory:
    """函数作用：构造长期记忆模型。
    输入参数：user_id - 所属用户 UUID；content - 记忆正文。
    输出参数：LongTermMemory 模型实例。
    """
    memory = LongTermMemory(
        user_id=user_id,
        content=content,
        metadata_={"title": "沟通偏好", "memory_key": "communication", "source": "manual"},
    )
    memory.id = uuid.uuid4()
    memory.created_at = datetime(2026, 5, 17, 1, 0, tzinfo=timezone.utc)
    memory.updated_at = datetime(2026, 5, 17, 1, 0, tzinfo=timezone.utc)
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


def test_memories_api_crud(monkeypatch):
    """函数作用：验证长期记忆 API 可新增、查看、更新和删除。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    user = build_user()
    memory = build_memory(user.id)
    install_auth_overrides(user)

    async def _helper_list_long_term_memories(_session, _user_id):
        return [memory]

    async def _helper_create_long_term_memory(_session, _user_id, title, memory_key, content, source):
        return build_memory(user.id, content)

    async def _helper_update_long_term_memory(_session, _user_id, _memory_id, title, memory_key, content, source):
        return build_memory(user.id, content)

    async def _helper_get_long_term_memory_by_id(_session, _user_id, _memory_id):
        return memory

    async def _helper_delete_long_term_memory(_session, _user_id, _memory_id):
        return True

    monkeypatch.setattr(memories_api, "list_long_term_memories", _helper_list_long_term_memories)
    monkeypatch.setattr(memories_api, "create_long_term_memory", _helper_create_long_term_memory)
    monkeypatch.setattr(memories_api, "update_long_term_memory", _helper_update_long_term_memory)
    monkeypatch.setattr(memories_api, "get_long_term_memory_by_id", _helper_get_long_term_memory_by_id)
    monkeypatch.setattr(memories_api, "delete_long_term_memory", _helper_delete_long_term_memory)

    client = TestClient(app)
    list_response = client.get("/api/memories")
    create_response = client.post(
        "/api/memories",
        json={"title": "沟通偏好", "memory_key": "communication", "content": "用户喜欢简洁回答"},
    )
    update_response = client.put(
        f"/api/memories/{memory.id}",
        json={"title": "沟通偏好", "memory_key": "communication", "content": "用户喜欢详细回答"},
    )
    delete_response = client.delete(f"/api/memories/{memory.id}")

    assert list_response.status_code == 200
    assert list_response.json()["memories"][0]["memoryKey"] == "communication"
    assert create_response.status_code == 200
    assert create_response.json()["memory"]["content"] == "用户喜欢简洁回答"
    assert update_response.status_code == 200
    assert update_response.json()["memory"]["content"] == "用户喜欢详细回答"
    assert delete_response.status_code == 200
    assert delete_response.json() == {"deleted_id": str(memory.id)}


def test_memories_api_returns_404_for_missing_memory(monkeypatch):
    """函数作用：验证更新不存在的长期记忆返回 404。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    user = build_user()
    install_auth_overrides(user)

    async def _helper_update_long_term_memory(*_args, **_kwargs):
        return None

    monkeypatch.setattr(memories_api, "update_long_term_memory", _helper_update_long_term_memory)

    response = TestClient(app).put(
        f"/api/memories/{uuid.uuid4()}",
        json={"title": "沟通偏好", "memory_key": "communication", "content": "用户喜欢详细回答"},
    )

    assert response.status_code == 404
    assert response.json() == {"error": {"code": "MEMORY_NOT_FOUND", "message": "长期记忆不存在"}}
