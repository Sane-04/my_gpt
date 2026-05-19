# 模块说明：后端核心配置与通用基础能力模块。
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse


class AppError(HTTPException):
    """类作用：携带业务错误码的 HTTP 异常。"""

    def __init__(self, status_code: int, code: str, message: str):
        """函数作用：初始化业务异常。
        输入参数：status_code - HTTP 状态码；code - 前端展示用错误码；message - 前端展示用错误信息。
        输出参数：无返回值。
        """
        super().__init__(status_code=status_code, detail={"code": code, "message": message})
        self.code = code
        self.message = message


async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    """函数作用：把 AppError 转成前端约定的错误响应。
    输入参数：_request - FastAPI 请求对象；exc - 业务异常。
    输出参数：JSONResponse，结构为 { error: { code, message } }。
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )
