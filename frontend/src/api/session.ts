// 模块说明：前端 API 模块，集中管理本地登录态的读取、写入和清理。
import type { AuthSession } from '@/types/auth'

const AUTH_SESSION_KEY = 'my_gpt_auth_session'

/**
 * 函数作用：读取并校验本地真实登录态。
 * 输入参数：无。
 * 输出参数：返回有效 AuthSession；无 session、过期或解析失败时返回 null。
 */
export function readStoredAuthSession(): AuthSession | null {
  const rawSession = localStorage.getItem(AUTH_SESSION_KEY)

  if (!rawSession) {
    return null
  }

  try {
    const session = JSON.parse(rawSession) as AuthSession

    // 结构不完整时立即清理，避免后续 store 读到半截数据。
    if (!session.token || !session.expiresAt || !session.user) {
      clearStoredAuthSession()
      return null
    }

    if (new Date(session.expiresAt).getTime() <= Date.now()) {
      clearStoredAuthSession()
      return null
    }

    return session
  } catch {
    // JSON 损坏通常来自手动编辑 localStorage，清理后要求用户重新登录。
    clearStoredAuthSession()
    return null
  }
}

/**
 * 函数作用：写入本地真实登录态。
 * 输入参数：session - 需要保存的 AuthSession。
 * 输出参数：无返回值。
 */
export function writeStoredAuthSession(session: AuthSession) {
  localStorage.setItem(AUTH_SESSION_KEY, JSON.stringify(session))
}

/**
 * 函数作用：清理本地真实登录态。
 * 输入参数：无。
 * 输出参数：无返回值。
 */
export function clearStoredAuthSession() {
  localStorage.removeItem(AUTH_SESSION_KEY)
}
