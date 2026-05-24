# 模块说明：后端 Grok 搜索 API 契约，定义请求、来源和响应结构。
from typing import Literal

from pydantic import BaseModel


class GrokSearchRequest(BaseModel):
    """类作用：定义 Grok 搜索请求体。"""

    query: str
    mode: Literal["web", "x", "auto"] = "web"


class GrokSearchSource(BaseModel):
    """类作用：定义 Grok 搜索来源展示字段。"""

    title: str | None = None
    url: str | None = None
    domain: str | None = None
    snippet: str | None = None


class GrokSearchResponse(BaseModel):
    """类作用：定义 Grok 搜索响应体。"""

    answer: str
    sources: list[GrokSearchSource]
    model: str
