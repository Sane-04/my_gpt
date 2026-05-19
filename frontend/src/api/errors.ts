// 模块说明：前端 API 模块，统一封装后端请求、错误归一化和流式响应。
import type { ApiErrorResponse } from '@/types/api'

// API 统一错误类型，store 捕获后只需要读取 message。
export class ApiError extends Error {
  code: string
  status?: number

  constructor(message: string, code = 'UNKNOWN_ERROR', status?: number) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
  }
}

/**
 * 函数作用：把未知错误归一化为 ApiError。
 * 输入参数：error - 任意捕获到的错误。
 * 输出参数：返回 ApiError。
 */
export function normalizeApiError(error: unknown) {
  if (error instanceof ApiError) {
    return error
  }

  if (error instanceof Error) {
    return new ApiError(error.message)
  }

  return new ApiError('请求失败，请稍后重试')
}

/**
 * 函数作用：从 HTTP 响应中解析标准错误结构。
 * 输入参数：response - fetch Response。
 * 输出参数：返回 ApiError。
 */
export async function createApiErrorFromResponse(response: Response) {
  try {
    const payload = (await response.json()) as ApiErrorResponse
    return new ApiError(
      payload.error?.message || '请求失败，请稍后重试',
      payload.error?.code || 'HTTP_ERROR',
      response.status,
    )
  } catch {
    return new ApiError(response.statusText || '请求失败，请稍后重试', 'HTTP_ERROR', response.status)
  }
}
