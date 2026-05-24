# 模块说明：后端测试模块，验证 Grok 搜索 API 契约和错误结构。
import uuid

import pytest
from fastapi.testclient import TestClient

from app.api import grok_search as grok_search_api
from app.api.deps import get_current_user
from app.main import app
from app.models.user import User
from app.services.grok_search_client import GrokSearchConfigError, GrokSearchRequestError


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    """函数作用：每个测试前后清理 FastAPI 依赖覆盖。
    输入参数：无。
    输出参数：无返回值。
    """
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def build_user() -> User:
    """函数作用：构造当前登录用户。
    输入参数：无。
    输出参数：User 模型实例。
    """
    user = User(email="tester@example.com", display_name="Tester", password_hash="hashed")
    user.id = uuid.uuid4()
    user.is_active = True
    return user


def install_auth_override(user: User):
    """函数作用：安装当前用户依赖覆盖。
    输入参数：user - 当前登录用户。
    输出参数：无返回值。
    """
    async def _helper_get_current_user():
        return user

    app.dependency_overrides[get_current_user] = _helper_get_current_user


def test_grok_search_requires_login():
    """函数作用：验证未登录不能访问 Grok 搜索。
    输入参数：无。
    输出参数：无返回值。
    """
    client = TestClient(app)

    response = client.post("/api/grok-search", json={"query": "测试"})

    assert response.status_code == 401


def test_grok_search_rejects_empty_query():
    """函数作用：验证空搜索内容返回输入错误。
    输入参数：无。
    输出参数：无返回值。
    """
    install_auth_override(build_user())
    client = TestClient(app)

    response = client.post("/api/grok-search", json={"query": "   "})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_GROK_SEARCH_INPUT"


def test_grok_search_returns_result(monkeypatch):
    """函数作用：验证 Grok 搜索成功响应契约。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值。
    """
    install_auth_override(build_user())

    class FakeGrokSearchClient:
        async def search(self, query, mode):
            return {
                "answer": f"回答：{query}/{mode}",
                "sources": [
                    {
                        "title": "来源标题",
                        "url": "https://example.com",
                        "domain": "example.com",
                        "snippet": "来源摘要",
                    }
                ],
                "model": "grok-4.3",
            }

    monkeypatch.setattr(grok_search_api, "GrokSearchClient", FakeGrokSearchClient)
    client = TestClient(app)

    response = client.post("/api/grok-search", json={"query": "今天新闻", "mode": "web"})

    assert response.status_code == 200
    assert response.json()["answer"] == "回答：今天新闻/web"
    assert response.json()["sources"][0]["domain"] == "example.com"
    assert response.json()["model"] == "grok-4.3"


def test_grok_search_returns_config_error(monkeypatch):
    """函数作用：验证 Grok 配置缺失返回标准错误。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值。
    """
    install_auth_override(build_user())

    class FakeGrokSearchClient:
        async def search(self, _query, _mode):
            raise GrokSearchConfigError("GROK_API_KEY 未配置")

    monkeypatch.setattr(grok_search_api, "GrokSearchClient", FakeGrokSearchClient)
    client = TestClient(app)

    response = client.post("/api/grok-search", json={"query": "测试"})

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "GROK_SEARCH_NOT_CONFIGURED"


def test_grok_search_returns_upstream_error(monkeypatch):
    """函数作用：验证 Grok 上游错误返回标准错误。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值。
    """
    install_auth_override(build_user())

    class FakeGrokSearchClient:
        async def search(self, _query, _mode):
            raise GrokSearchRequestError("Grok 搜索 HTTP 调用失败：502")

    monkeypatch.setattr(grok_search_api, "GrokSearchClient", FakeGrokSearchClient)
    client = TestClient(app)

    response = client.post("/api/grok-search", json={"query": "测试"})

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "GROK_SEARCH_FAILED"
