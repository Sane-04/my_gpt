// 模块说明：前端 API 模块，统一封装后端请求、错误归一化和流式响应。
import { createApiErrorFromResponse } from '@/api/errors'
import { readStoredAuthSession } from '@/api/session'

// 前端环境模式：production 使用公网域名，其他模式默认连接本地后端。
const APP_ENV = import.meta.env.VITE_APP_ENV || 'development'
const PUBLIC_API_BASE_URL = import.meta.env.VITE_PUBLIC_API_BASE_URL || ''
const API_BASE_URL = APP_ENV === 'production' ? PUBLIC_API_BASE_URL : 'http://127.0.0.1:8000'
export const AUTH_EXPIRED_EVENT = 'my-gpt:auth-expired'

/**
 * 函数作用：拼接后端 API 完整 URL。
 * 输入参数：path - 以 / 开头的 API 路径。
 * 输出参数：返回完整请求 URL。
 */
function buildApiUrl(path: string) {
  return `${API_BASE_URL}${path}`
}

/**
 * 函数作用：生成 HTTP 请求头，自动携带真实登录 token。
 * 输入参数：headers - 调用方额外传入的请求头。
 * 输出参数：返回 Headers 对象。
 */
function buildHeaders(headers?: HeadersInit) {
  const nextHeaders = new Headers(headers)
  const session = readStoredAuthSession()

  if (!nextHeaders.has('Content-Type')) {
    nextHeaders.set('Content-Type', 'application/json')
  }

  if (session?.token) {
    nextHeaders.set('Authorization', `Bearer ${session.token}`)
  }

  return nextHeaders
}

/** 函数作用：通知应用当前登录态已被后端拒绝；输入参数：无；输出参数：无返回值。 */
function emitAuthExpired() {
  window.dispatchEvent(new CustomEvent(AUTH_EXPIRED_EVENT))
}

/**
 * 函数作用：封装 JSON HTTP 请求和标准错误解析。
 * 输入参数：path - API 路径；options - fetch 配置。
 * 输出参数：返回解析后的 JSON 数据。
 */
export async function apiFetch<T>(path: string, options: RequestInit = {}) {
  const response = await fetch(buildApiUrl(path), {
    ...options,
    headers: buildHeaders(options.headers),
  })

  if (!response.ok) {
    if (response.status === 401) {
      emitAuthExpired()
    }
    throw await createApiErrorFromResponse(response)
  }

  return (await response.json()) as T
}

/**
 * 函数作用：封装真实 fetch stream 请求。
 * 输入参数：path - API 路径；options - fetch 配置。
 * 输出参数：返回 ReadableStream。
 */
export async function apiStream(path: string, options: RequestInit = {}) {
  const response = await fetch(buildApiUrl(path), {
    ...options,
    headers: buildHeaders(options.headers),
  })

  if (!response.ok) {
    if (response.status === 401) {
      emitAuthExpired()
    }
    throw await createApiErrorFromResponse(response)
  }

  if (!response.body) {
    throw new Error('流式响应为空')
  }

  return response.body
}
