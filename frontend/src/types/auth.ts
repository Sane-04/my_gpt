// 模块说明：前端类型模块，定义领域对象、请求响应和流式事件契约。
import type { User } from '@/types/domain'

// 登录页模式：同一个页面在登录和注册之间切换。
export type AuthMode = 'login' | 'register'

// 注册请求契约，后端实现时应保持字段名兼容。
export interface RegisterRequest {
  email: string
  password: string
  displayName: string
}

// 登录请求契约，第一阶段只使用邮箱和密码。
export interface LoginRequest {
  email: string
  password: string
}

// Auth API 返回结构，expires_at 保持 snake_case 以贴近 HTTP API 契约。
export interface AuthResponse {
  token: string
  expires_at: string
  user: User
}

// 当前用户接口返回结构，用于刷新后恢复用户信息。
export interface MeResponse {
  user: User
}

// 前端本地 session 存储结构，写入 localStorage 时使用 expiresAt。
export interface AuthSession {
  token: string
  expiresAt: string
  user: User
}
