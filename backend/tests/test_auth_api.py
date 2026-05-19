# 模块说明：后端测试模块，验证接口契约、仓储行为和核心服务边界。
import uuid

import pytest
from fastapi.testclient import TestClient

from app.api import auth as auth_api
from app.api import deps as api_deps
from app.core.security import create_access_token, hash_password
from app.db import get_db
from app.main import app
from app.models.user import User


class DummySession:
    """类作用：为 Auth API 测试提供不连接数据库的占位 Session。"""


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


def build_user(email: str = "tester@example.com", password: str = "password") -> User:
    """函数作用：构造测试用用户模型。
    输入参数：email - 用户邮箱；password - 明文密码，用于生成哈希。
    输出参数：User 模型实例。
    """
    user = User(
        email=email,
        display_name="Tester",
        password_hash=hash_password(password),
    )
    user.id = uuid.uuid4()
    user.is_active = True
    return user


def test_register_returns_frontend_auth_contract(monkeypatch):
    """函数作用：验证注册接口返回前端 Auth 契约。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    captured_password_hash = ""
    app.dependency_overrides[get_db] = override_get_db

    async def _helper_get_user_by_email(_session, _email):
        return None

    async def _helper_create_user(session, email, display_name, password_hash):
        nonlocal captured_password_hash
        captured_password_hash = password_hash
        user = build_user(email=email)
        user.display_name = display_name
        user.password_hash = password_hash
        return user

    monkeypatch.setattr(auth_api, "get_user_by_email", _helper_get_user_by_email)
    monkeypatch.setattr(auth_api, "create_user", _helper_create_user)

    response = TestClient(app).post(
        "/api/auth/register",
        json={"email": "Tester@Example.com", "password": "password", "displayName": "Tester"},
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["token"]
    assert payload["expires_at"]
    assert payload["user"]["email"] == "tester@example.com"
    assert payload["user"]["displayName"] == "Tester"
    assert captured_password_hash != "password"


def test_register_rejects_duplicate_email(monkeypatch):
    """函数作用：验证重复邮箱注册会返回标准错误结构。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    app.dependency_overrides[get_db] = override_get_db

    async def _helper_get_user_by_email(_session, _email):
        return build_user()

    monkeypatch.setattr(auth_api, "get_user_by_email", _helper_get_user_by_email)

    response = TestClient(app).post(
        "/api/auth/register",
        json={"email": "tester@example.com", "password": "password", "displayName": "Tester"},
    )

    assert response.status_code == 409
    assert response.json() == {"error": {"code": "EMAIL_ALREADY_REGISTERED", "message": "邮箱已注册"}}


def test_login_returns_token_for_valid_password(monkeypatch):
    """函数作用：验证登录接口在密码正确时返回 token。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    app.dependency_overrides[get_db] = override_get_db
    user = build_user(password="password")

    async def _helper_get_user_by_email(_session, _email):
        return user

    monkeypatch.setattr(auth_api, "get_user_by_email", _helper_get_user_by_email)

    response = TestClient(app).post(
        "/api/auth/login",
        json={"email": "tester@example.com", "password": "password"},
    )

    assert response.status_code == 200
    assert response.json()["token"]


def test_login_rejects_wrong_password(monkeypatch):
    """函数作用：验证密码错误时登录失败。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    app.dependency_overrides[get_db] = override_get_db
    user = build_user(password="password")

    async def _helper_get_user_by_email(_session, _email):
        return user

    monkeypatch.setattr(auth_api, "get_user_by_email", _helper_get_user_by_email)

    response = TestClient(app).post(
        "/api/auth/login",
        json={"email": "tester@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json() == {"error": {"code": "INVALID_CREDENTIALS", "message": "邮箱或密码错误"}}


def test_me_requires_token():
    """函数作用：验证未携带 token 访问 me 会失败。
    输入参数：无。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    app.dependency_overrides[get_db] = override_get_db

    response = TestClient(app).get("/api/auth/me")

    assert response.status_code == 401
    assert response.json() == {"error": {"code": "UNAUTHORIZED", "message": "请先登录"}}


def test_me_returns_current_user(monkeypatch):
    """函数作用：验证携带有效 token 时 me 返回当前用户。
    输入参数：monkeypatch - pytest monkeypatch fixture。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    app.dependency_overrides[get_db] = override_get_db
    user = build_user()
    token, _expires_at = create_access_token(user.id)

    async def _helper_get_user_by_id(_session, _user_id):
        return user

    monkeypatch.setattr(api_deps, "get_user_by_id", _helper_get_user_by_id)

    response = TestClient(app).get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {
        "user": {
            "id": str(user.id),
            "email": "tester@example.com",
            "displayName": "Tester",
        }
    }
