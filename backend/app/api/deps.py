# 模块说明：后端 API 路由模块，负责请求校验、鉴权依赖和响应契约转换。
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import decode_access_token
from app.db import get_db
from app.models.user import User
from app.repositories.users import get_user_by_id


# Bearer 鉴权依赖：auto_error=False 让我们返回统一错误结构。
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db),
) -> User:
    """函数作用：从 Authorization Bearer Token 获取当前登录用户。
    输入参数：credentials - HTTP Bearer 凭证；session - 异步数据库会话。
    输出参数：返回当前用户；未登录或 token 无效时抛出 AppError。
    """
    if credentials is None:
        raise AppError(status_code=401, code="UNAUTHORIZED", message="请先登录")

    try:
        user_id = decode_access_token(credentials.credentials)
    except (JWTError, ValueError):
        raise AppError(status_code=401, code="INVALID_TOKEN", message="登录已过期，请重新登录")

    user = await get_user_by_id(session, user_id)
    if user is None or not user.is_active:
        raise AppError(status_code=401, code="INVALID_TOKEN", message="登录已过期，请重新登录")

    return user
