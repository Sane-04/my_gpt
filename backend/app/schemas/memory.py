# 模块说明：后端 Pydantic 契约模块，定义请求体和响应体结构。
from pydantic import BaseModel, Field


class MemoryCreateRequest(BaseModel):
    """类作用：描述新增长期记忆请求体。"""

    title: str = Field(min_length=1, max_length=200)
    memory_key: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1)
    source: str | None = Field(default="manual", max_length=40)


class MemoryUpdateRequest(BaseModel):
    """类作用：描述更新长期记忆请求体。"""

    title: str = Field(min_length=1, max_length=200)
    memory_key: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1)
    source: str | None = Field(default="manual", max_length=40)


class MemoryResponse(BaseModel):
    """类作用：描述前端 LongTermMemory 领域对象。"""

    id: str
    title: str
    memoryKey: str
    content: str
    source: str
    createdAt: str
    updatedAt: str


class MemoryListResponse(BaseModel):
    """类作用：描述长期记忆列表响应。"""

    memories: list[MemoryResponse]


class MemoryDetailResponse(BaseModel):
    """类作用：描述单条长期记忆响应。"""

    memory: MemoryResponse


class DeleteMemoryResponse(BaseModel):
    """类作用：描述删除长期记忆响应。"""

    deleted_id: str
