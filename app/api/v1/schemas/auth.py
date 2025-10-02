"""认证相关的请求与响应模型。"""

from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.api.v1.schemas.common import ResponseEnvelope


class RegisterRequest(BaseModel):
    """用户注册时需要提交的字段约束。"""

    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)
    organization_id: int = Field(..., ge=1)


class LoginRequest(BaseModel):
    """登录请求的字段校验规则。"""

    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)


class RegisterResponseData(BaseModel):
    """注册成功后返回给前端的用户关键信息。"""

    user_id: int
    username: str
    organization: Optional[dict]
    roles: list[str]


class TokenResponseData(BaseModel):
    """登录成功后签发的令牌信息。"""

    access_token: str
    token_type: Literal["bearer"]


RegisterResponse = ResponseEnvelope[RegisterResponseData]
TokenResponse = ResponseEnvelope[TokenResponseData]
LogoutResponse = ResponseEnvelope[None]
