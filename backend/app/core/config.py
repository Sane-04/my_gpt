# 模块说明：后端核心配置与通用基础能力模块。
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


load_dotenv("backend/.env")
load_dotenv(".env")


class Settings(BaseSettings):
    """类作用：集中管理后端运行配置。"""

    # 配置来源：优先读取 backend/.env，兼容从 backend 目录内执行命令时读取 .env。
    model_config = SettingsConfigDict(extra="ignore")

    # 数据库连接串：SQLAlchemy 异步 engine 使用 asyncpg 驱动连接 PostgreSQL。
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:sane@127.0.0.1:5432/my_gpt",
        alias="DATABASE_URL",
    )
    # JWT 配置：后续登录鉴权任务会使用这些参数签发和校验 Token。
    jwt_secret: str = Field(default="sane", alias="JWT_SECRET")
    jwt_expire_days: int = Field(default=7, alias="JWT_EXPIRE_DAYS")
    # 模型配置：兼容 OpenAI 官方接口或同协议服务。
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    chat_model: str = Field(default="gpt-5.4", validation_alias=AliasChoices("CHAT_MODEL", "RESPONSES_MODEL"))
    # 图片生成配置：使用 Image API 调用专用图片模型，聊天模型仅负责意图识别和普通对话。
    image_model: str = Field(default="gpt-image-2", alias="IMAGE_MODEL")
    image_size: str = Field(default="1024x1024", alias="IMAGE_SIZE")
    image_quality: str = Field(default="high", alias="IMAGE_QUALITY")
    image_output_format: str = Field(default="png", alias="IMAGE_OUTPUT_FORMAT")
    image_intent_context_size: int = Field(default=5, alias="IMAGE_INTENT_CONTEXT_SIZE")
    image_http_timeout_seconds: float = Field(default=360.0, alias="IMAGE_HTTP_TIMEOUT_SECONDS")
    # Embedding 配置：独立于聊天模型配置，避免不同供应商或网关混用鉴权信息。
    embedding_api_key: str = Field(default="", alias="EMBEDDING_API_KEY")
    embedding_base_url: str = Field(default="", alias="EMBEDDING_BASE_URL")
    embedding_model: str = Field(default="text-embedding-3-small", alias="EMBEDDING_MODEL")
    # 联网搜索配置：使用 SerpApi Google Search API 获取通用网页搜索结果。
    web_search_provider: str = Field(default="serpapi", alias="WEB_SEARCH_PROVIDER")
    serpapi_api_key: str = Field(default="", alias="SERPAPI_API_KEY")
    serpapi_timeout_seconds: float = Field(default=15.0, alias="SERPAPI_TIMEOUT_SECONDS")
    # Grok 搜索配置：独立于主聊天模型，用作聊天联网搜索 provider。
    grok_api_key: str = Field(default="", alias="GROK_API_KEY")
    grok_base_url: str = Field(default="https://api.x.ai/v1", alias="GROK_BASE_URL")
    grok_search_model: str = Field(default="grok-4.3", alias="GROK_SEARCH_MODEL")
    grok_search_timeout_seconds: float = Field(default=60.0, alias="GROK_SEARCH_TIMEOUT_SECONDS")
    grok_search_max_results: int = Field(default=5, alias="GROK_SEARCH_MAX_RESULTS")
    # 模型请求超时：流式读取超时用于避免上游网关挂起时聊天一直处于生成中。
    model_http_timeout_seconds: float = Field(default=60.0, alias="MODEL_HTTP_TIMEOUT_SECONDS")
    model_stream_timeout_seconds: float = Field(default=180.0, alias="MODEL_STREAM_TIMEOUT_SECONDS")
    # 上下文与长期记忆配置：控制模型请求拼装时的消息窗口和记忆文本上限。
    context_window_size: int = Field(default=5, alias="CONTEXT_WINDOW_SIZE")
    long_term_memory_max_chars: int = Field(default=20000, alias="LONG_TERM_MEMORY_MAX_CHARS")
    # 调试配置：生产环境默认不保存 prompt_snapshots，避免持久化敏感提示词。
    save_prompt_snapshots: bool = Field(default=False, alias="SAVE_PROMPT_SNAPSHOTS")
    memory_dir: str = Field(default="backend/data/memories", alias="MEMORY_DIR")
    # CORS 配置：允许本地前端开发服务器跨域访问后端 API。
    cors_origins: list[str] = Field(default=["http://localhost:5173", "http://127.0.0.1:5173"], alias="CORS_ORIGINS")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        """函数作用：把环境变量中的 CORS 源解析为列表。
        输入参数：value - 字符串或字符串列表。
        输出参数：CORS 源列表。
        """
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]

        return value


@lru_cache
def get_settings() -> Settings:
    """函数作用：返回缓存后的后端配置。
    输入参数：无。
    输出参数：Settings 配置对象。
    """
    return Settings()
