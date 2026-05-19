// 模块说明：前端 Pinia 状态模块，集中管理跨组件共享状态和异步动作。
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { authApi, writeStoredAuthSession } from '@/api'
import { useAuthStore } from '@/stores/auth'

describe('useAuthStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('可以注册、恢复并退出真实登录态', async () => {
    const authStore = useAuthStore()
    const authResponse = {
      token: 'jwt-token',
      expires_at: new Date(Date.now() + 86_400_000).toISOString(),
      user: {
        id: 'user-1',
        email: 'tester@example.com',
        displayName: 'Tester',
      },
    }
    vi.spyOn(authApi, 'register').mockResolvedValue(authResponse)

    await authStore.register({
      email: 'tester@example.com',
      password: 'password',
      displayName: 'Tester',
    })

    expect(authStore.isAuthenticated).toBe(true)
    expect(authStore.user?.email).toBe('tester@example.com')

    writeStoredAuthSession({
      token: authResponse.token,
      expiresAt: authResponse.expires_at,
      user: authResponse.user,
    })
    const restoredStore = useAuthStore()
    restoredStore.restoreSession()
    expect(restoredStore.user?.displayName).toBe('Tester')

    authStore.logout()
    expect(authStore.isAuthenticated).toBe(false)
  })
})
