# 模块说明：后端数据库基础设施模块，集中声明 ORM 基类、引擎和会话依赖。
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings


settings = get_settings()

# 异步数据库引擎：应用运行期所有数据库连接都从这里创建。
engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
)

# 异步 Session 工厂：expire_on_commit=False 让提交后对象属性仍可读取。
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """函数作用：为 FastAPI 依赖注入提供异步数据库会话。
    输入参数：无。
    输出参数：异步生成一个 AsyncSession。
    """
    async with AsyncSessionLocal() as session:
        yield session
