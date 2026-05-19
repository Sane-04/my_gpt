# 模块说明：后端测试模块，验证接口契约、仓储行为和核心服务边界。
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal, engine


def test_settings_default_database_url_is_async_postgresql():
    """函数作用：验证默认数据库连接串使用 PostgreSQL 异步驱动。
    输入参数：无。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    # 默认连接串必须使用 asyncpg 异步方言，匹配 SQLAlchemy 2 async engine。
    settings = get_settings()

    assert settings.database_url.startswith("postgresql+asyncpg://")


def test_async_session_factory_creates_async_session():
    """函数作用：验证异步 Session 工厂可以创建 AsyncSession。
    输入参数：无。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    # Session 工厂不需要真实连接数据库即可创建 AsyncSession 对象。
    session = AsyncSessionLocal()

    try:
        assert isinstance(session, AsyncSession)
    finally:
        assert session.sync_session is not None


def test_engine_uses_configured_database_url():
    """函数作用：验证异步 engine 使用配置中的数据库连接信息。
    输入参数：无。
    输出参数：无返回值，断言失败时由 pytest 报错。
    """
    # SQLAlchemy 默认隐藏密码，测试时显式渲染完整 URL 与配置比对。
    settings = get_settings()

    assert engine.url.render_as_string(hide_password=False) == settings.database_url
