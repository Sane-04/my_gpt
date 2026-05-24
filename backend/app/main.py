# 模块说明：后端应用入口，创建 FastAPI 实例并挂载中间件、异常处理器和路由。
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth_router, chat_router, conversations_router, grok_search_router, memories_router
from app.core.config import get_settings
from app.core.errors import AppError, app_error_handler

app = FastAPI(title="My GPT Backend")
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_exception_handler(AppError, app_error_handler)
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(conversations_router)
app.include_router(grok_search_router)
app.include_router(memories_router)


@app.get("/health")
def health_check():
    """函数作用：返回后端健康检查状态。
    输入参数：无。
    输出参数：包含服务状态和服务名的字典。
    """
    return {"status": "ok", "service": "my-gpt-backend"}
