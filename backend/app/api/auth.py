# 模块说明：后端 API 路由模块，负责请求校验、鉴权依赖和响应契约转换。
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.errors import AppError
from app.core.security import create_access_token, hash_password, verify_password
from app.db import get_db
from app.models.user import User
from app.repositories.users import create_user, get_user_by_email
from app.schemas.auth import AuthResponse, LoginRequest, MeResponse, RegisterRequest, UserResponse


router = APIRouter(prefix="/api/auth", tags=["auth"])


def _serialize_user(user: User) -> UserResponse:
    """函数作用：把数据库用户模型转成前端 Auth 契约用户对象。
    输入参数：user - 数据库用户模型。
    输出参数：UserResponse，字段保持 id、email、displayName。
    """
    return UserResponse(
        id=str(user.id),
        email=user.email,
        displayName=user.display_name or user.email.split("@")[0],
    )


def _build_auth_response(user: User, token: str, expires_at: datetime) -> AuthResponse:
    """函数作用：组装注册和登录接口响应。
    输入参数：user - 当前用户；token - JWT 字符串；expires_at - token 过期时间。
    输出参数：AuthResponse，兼容前端 localStorage 登录态。
    """
    return AuthResponse(
        token=token,
        expires_at=expires_at.isoformat(),
        user=_serialize_user(user),
    )


@router.post("/register", response_model=AuthResponse)
async def register(request: RegisterRequest, session: AsyncSession = Depends(get_db)) -> AuthResponse:
    """函数作用：注册新用户并返回 JWT 登录态。
    输入参数：request - 注册请求体；session - 异步数据库会话。
    输出参数：AuthResponse，包含 token、expires_at 和 user。
    """
    email = request.email.strip().lower()
    display_name = request.displayName.strip()

    if not email or not display_name:
        raise AppError(status_code=400, code="INVALID_AUTH_INPUT", message="请输入邮箱和昵称")

    existing_user = await get_user_by_email(session, email)
    if existing_user is not None:
        raise AppError(status_code=409, code="EMAIL_ALREADY_REGISTERED", message="邮箱已注册")

    user = await create_user(
        session=session,
        email=email,
        display_name=display_name,
        password_hash=hash_password(request.password),
    )
    token, expires_at = create_access_token(user.id)
    return _build_auth_response(user, token, expires_at)


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest, session: AsyncSession = Depends(get_db)) -> AuthResponse:
    """函数作用：校验邮箱密码并返回 JWT 登录态。
    输入参数：request - 登录请求体；session - 异步数据库会话。
    输出参数：AuthResponse，包含 token、expires_at 和 user。
    """
    email = request.email.strip().lower()
    user = await get_user_by_email(session, email)

    if user is None or not user.is_active or not verify_password(request.password, user.password_hash):
        raise AppError(status_code=401, code="INVALID_CREDENTIALS", message="邮箱或密码错误")

    token, expires_at = create_access_token(user.id)
    return _build_auth_response(user, token, expires_at)


@router.get("/me", response_model=MeResponse)
async def me(current_user: User = Depends(get_current_user)) -> MeResponse:
    """函数作用：返回当前登录用户信息。
    输入参数：current_user - 由 get_current_user 解析出的当前用户。
    输出参数：MeResponse，包含 user。
    """
    return MeResponse(user=_serialize_user(current_user))
