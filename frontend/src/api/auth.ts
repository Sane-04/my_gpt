// 模块说明：前端 API 模块，统一封装后端请求、错误归一化和流式响应。
import { apiFetch } from '@/api/http'
import { writeStoredAuthSession } from '@/api/session'
import type { AuthResponse, LoginRequest, MeResponse, RegisterRequest } from '@/types/auth'

// 认证 API：只保留真实后端接口调用，登录态持久化由 session 模块负责。
export const authApi = {
  async register(request: RegisterRequest) {
    const response = await apiFetch<AuthResponse>('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify(request),
    })
    writeStoredAuthSession({
      token: response.token,
      expiresAt: response.expires_at,
      user: response.user,
    })
    return response
  },
  async login(request: LoginRequest) {
    const response = await apiFetch<AuthResponse>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify(request),
    })
    writeStoredAuthSession({
      token: response.token,
      expiresAt: response.expires_at,
      user: response.user,
    })
    return response
  },
  me() {
    return apiFetch<MeResponse>('/api/auth/me')
  },
}
