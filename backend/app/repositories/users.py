# 模块说明：后端仓储模块，封装数据库读写细节并保持用户数据隔离。
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    """函数作用：按邮箱查询用户。
    输入参数：session - 异步数据库会话；email - 已归一化的小写邮箱。
    输出参数：找到时返回 User，否则返回 None。
    """
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    """函数作用：按用户 UUID 查询用户。
    输入参数：session - 异步数据库会话；user_id - 用户 UUID。
    输出参数：找到时返回 User，否则返回 None。
    """
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def create_user(session: AsyncSession, email: str, display_name: str, password_hash: str) -> User:
    """函数作用：创建新用户并提交事务。
    输入参数：session - 异步数据库会话；email - 已归一化邮箱；display_name - 展示名；password_hash - 密码哈希。
    输出参数：返回已刷新主键和时间字段的 User。
    """
    user = User(email=email, display_name=display_name, password_hash=password_hash)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user
