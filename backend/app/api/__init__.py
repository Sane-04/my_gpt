# 模块说明：后端 API 路由模块，负责请求校验、鉴权依赖和响应契约转换。
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.conversations import router as conversations_router
from app.api.memories import router as memories_router

__all__ = ["auth_router", "chat_router", "conversations_router", "memories_router"]
