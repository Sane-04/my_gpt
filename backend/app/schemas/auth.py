# 模块说明：后端 Pydantic 契约模块，定义请求体和响应体结构。
from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    """类作用：描述注册接口请求体。"""

    # email 和 displayName 使用前端既有 camelCase 契约，避免联调时额外转换。
    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=128)
    displayName: str = Field(min_length=1, max_length=120)


class LoginRequest(BaseModel):
    """类作用：描述登录接口请求体。"""

    # 登录阶段只需要邮箱和密码，不引入复杂权限字段。
    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    """类作用：描述前端 Auth 契约中的用户对象。"""

    id: str
    email: str
    displayName: str


class AuthResponse(BaseModel):
    """类作用：描述注册和登录成功响应。"""

    token: str
    expires_at: str
    user: UserResponse


class MeResponse(BaseModel):
    """类作用：描述当前用户接口响应。"""

    user: UserResponse
