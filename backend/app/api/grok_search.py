# 模块说明：后端 Grok 搜索 API，提供独立于聊天链路的搜索入口。
from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.core.errors import AppError
from app.models.user import User
from app.schemas.grok_search import GrokSearchRequest, GrokSearchResponse
from app.services.grok_search_client import GrokSearchClient, GrokSearchConfigError, GrokSearchRequestError


router = APIRouter(prefix="/api/grok-search", tags=["grok-search"])


@router.post("", response_model=GrokSearchResponse)
async def search_grok(
    request: GrokSearchRequest,
    _current_user: User = Depends(get_current_user),
) -> GrokSearchResponse:
    """函数作用：执行独立 Grok 搜索。
    输入参数：request - Grok 搜索请求体；_current_user - 当前登录用户。
    输出参数：GrokSearchResponse 搜索回答与来源。
    """
    query = request.query.strip()
    if not query:
        raise AppError(status_code=400, code="INVALID_GROK_SEARCH_INPUT", message="搜索内容不能为空")

    client = GrokSearchClient()
    try:
        result = await client.search(query, request.mode)
    except GrokSearchConfigError as exc:
        raise AppError(status_code=500, code="GROK_SEARCH_NOT_CONFIGURED", message=str(exc)) from exc
    except GrokSearchRequestError as exc:
        message = str(exc)
        if "超时" in message:
            raise AppError(status_code=504, code="GROK_SEARCH_TIMEOUT", message=message) from exc
        if "无法解析" in message or "缺少回答内容" in message:
            raise AppError(status_code=502, code="GROK_SEARCH_INVALID_RESPONSE", message=message) from exc
        raise AppError(status_code=502, code="GROK_SEARCH_FAILED", message=message) from exc

    return GrokSearchResponse(**result)
