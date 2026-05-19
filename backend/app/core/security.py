# 模块说明：后端核心配置与通用基础能力模块。
import uuid
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings


# 密码哈希上下文：bcrypt 只保存不可逆哈希，后续可在这里平滑升级算法。
password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """函数作用：对明文密码进行 bcrypt 哈希。
    输入参数：password - 用户提交的明文密码。
    输出参数：返回可持久化保存的密码哈希。
    """
    return password_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """函数作用：校验明文密码是否匹配密码哈希。
    输入参数：password - 用户提交的明文密码；password_hash - 数据库中保存的密码哈希。
    输出参数：匹配时返回 True，否则返回 False。
    """
    return password_context.verify(password, password_hash)


def create_access_token(user_id: uuid.UUID) -> tuple[str, datetime]:
    """函数作用：为指定用户创建 JWT 访问令牌。
    输入参数：user_id - 用户 UUID。
    输出参数：返回 JWT 字符串和过期时间。
    """
    settings = get_settings()
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.jwt_expire_days)
    payload = {
        "sub": str(user_id),
        "exp": expires_at,
        "type": "access",
    }

    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM), expires_at


def decode_access_token(token: str) -> uuid.UUID:
    """函数作用：解析 JWT 并提取用户 UUID。
    输入参数：token - Authorization Bearer 中的 JWT。
    输出参数：返回 token 中的用户 UUID；无效时抛出 JWTError 或 ValueError。
    """
    settings = get_settings()
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])

    if payload.get("type") != "access":
        raise JWTError("invalid token type")

    subject = payload.get("sub")
    if not subject:
        raise JWTError("missing subject")

    return uuid.UUID(subject)
