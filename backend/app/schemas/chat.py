# 模块说明：后端 Pydantic 契约模块，定义请求体和响应体结构。
from pydantic import BaseModel, Field, field_validator, model_validator


ALLOWED_IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
MAX_CHAT_IMAGE_COUNT = 5
MAX_CHAT_IMAGE_SIZE_BYTES = 10 * 1024 * 1024


class ChatImageInput(BaseModel):
    """类作用：描述聊天请求中的 Base64 图片输入。"""

    name: str = Field(min_length=1, max_length=255)
    mimeType: str = Field(min_length=1)
    size: int = Field(ge=1, le=MAX_CHAT_IMAGE_SIZE_BYTES)
    dataUrl: str = Field(min_length=1)

    @field_validator("mimeType")
    @classmethod
    def validate_mime_type(cls, value: str) -> str:
        """函数作用：校验图片 MIME 类型。
        输入参数：value - 前端传入的 MIME 类型。
        输出参数：合法 MIME 类型；非法时抛出 ValueError。
        """
        if value not in ALLOWED_IMAGE_MIME_TYPES:
            raise ValueError("仅支持 png、jpeg、webp、gif 图片")

        return value

    @model_validator(mode="after")
    def validate_data_url(self):
        """函数作用：校验 data URL 与 MIME 类型一致。
        输入参数：无。
        输出参数：当前图片输入对象；非法时抛出 ValueError。
        """
        expected_prefix = f"data:{self.mimeType};base64,"
        if not self.dataUrl.startswith(expected_prefix):
            raise ValueError("图片 dataUrl 格式不正确")

        return self


class ChatStreamRequest(BaseModel):
    """类作用：描述聊天流式接口请求体。"""

    # conversationId 保持前端 SendMessageInput 的 camelCase 契约。
    conversationId: str = Field(min_length=1)
    content: str = ""
    enableWebSearch: bool = False
    images: list[ChatImageInput] = Field(default_factory=list, max_length=MAX_CHAT_IMAGE_COUNT)

    @model_validator(mode="after")
    def validate_content_or_images(self):
        """函数作用：校验聊天请求至少包含文字或图片。
        输入参数：无。
        输出参数：当前请求对象；非法时抛出 ValueError。
        """
        if not self.content.strip() and not self.images:
            raise ValueError("消息内容不能为空")

        return self
