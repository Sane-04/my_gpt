# 模块说明：后端 Pydantic 契约模块，定义请求体和响应体结构。
from pydantic import BaseModel, Field


class ConversationCreateRequest(BaseModel):
    """类作用：描述创建会话接口请求体。"""

    # title 保持前端 CreateConversationRequest 契约，后端会做 trim 和默认值兜底。
    title: str | None = Field(default=None, max_length=200)


class ConversationResponse(BaseModel):
    """类作用：描述前端 Conversation 领域对象。"""

    id: str
    title: str
    createdAt: str | None = None
    updatedAt: str


class ConversationDetailResponse(BaseModel):
    """类作用：描述单个会话响应。"""

    conversation: ConversationResponse


class ConversationListResponse(BaseModel):
    """类作用：描述会话列表响应。"""

    conversations: list[ConversationResponse]


class DeleteConversationResponse(BaseModel):
    """类作用：描述硬删除会话响应。"""

    deleted_id: str


class MessageResponse(BaseModel):
    """类作用：描述前端 Message 领域对象。"""

    id: str
    conversationId: str
    role: str
    content: str
    createdAt: str
    status: str = "complete"
    toolName: str | None = None
    images: list[dict] | None = None
    sources: list[dict] | None = None
    citationGroups: list[dict] | None = None


class ConversationMessagesResponse(BaseModel):
    """类作用：描述指定会话的消息列表响应。"""

    messages: list[MessageResponse]
    # hasMore 表示是否还能继续向上翻页加载更早消息。
    hasMore: bool = False
