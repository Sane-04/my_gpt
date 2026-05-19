// 模块说明：前端 Pinia 状态模块，集中管理跨组件共享状态和异步动作。
import { defineStore } from 'pinia'
import { authApi, clearStoredAuthSession, readStoredAuthSession } from '@/api'
import type { LoginRequest, RegisterRequest } from '@/types/auth'
import type { User } from '@/types/domain'

// Auth store 负责把真实 API、localStorage session 和页面状态统一起来。
export const useAuthStore = defineStore('auth', {
  state: () => ({
    // 当前用户信息；为 null 时表示未登录。
    user: null as User | null,
    // 后端签发的 JWT，会放到 Authorization header。
    token: null as string | null,
    // 本地登录态过期时间，刷新恢复时用于判断 session 是否有效。
    expiresAt: null as string | null,
    // 登录/注册按钮的加载状态。
    isLoading: false,
    // 表单可展示的错误信息。
    errorMessage: '',
  }),
  getters: {
    // 只要有 user 就认为前端处于已登录态。
    isAuthenticated: (state) => Boolean(state.user),
  },
  actions: {
    /** 函数作用：调用后端注册接口并写入 store；输入参数：request 注册表单；输出参数：Promise<void>。 */
    async register(request: RegisterRequest) {
      this.isLoading = true
      this.errorMessage = ''

      try {
        const response = await authApi.register(request)
        this.token = response.token
        this.expiresAt = response.expires_at
        this.user = response.user
      } catch (error) {
        this.errorMessage = error instanceof Error ? error.message : '注册失败，请稍后重试'
        throw error
      } finally {
        this.isLoading = false
      }
    },
    /** 函数作用：调用后端登录接口并写入 store；输入参数：request 登录表单；输出参数：Promise<void>。 */
    async login(request: LoginRequest) {
      this.isLoading = true
      this.errorMessage = ''

      try {
        const response = await authApi.login(request)
        this.token = response.token
        this.expiresAt = response.expires_at
        this.user = response.user
      } catch (error) {
        this.errorMessage = error instanceof Error ? error.message : '登录失败，请稍后重试'
        throw error
      } finally {
        this.isLoading = false
      }
    },
    /** 函数作用：应用启动时恢复本地 session；输入参数：无；输出参数：无返回值。 */
    restoreSession() {
      const session = readStoredAuthSession()

      if (!session) {
        this.token = null
        this.expiresAt = null
        this.user = null
        return
      }

      this.token = session.token
      this.expiresAt = session.expiresAt
      this.user = session.user
    },
    /** 函数作用：退出登录并清理本地 session；输入参数：无；输出参数：无返回值。 */
    logout() {
      clearStoredAuthSession()
      this.token = null
      this.expiresAt = null
      this.user = null
      this.errorMessage = ''
    },
  },
})
