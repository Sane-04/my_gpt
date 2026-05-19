// 模块说明：前端 API 测试模块，验证统一 HTTP 封装的边界行为。
import { describe, expect, it, vi } from 'vitest'
import { AUTH_EXPIRED_EVENT, apiFetch } from '@/api/http'

describe('api http', () => {
  it('收到 401 时会派发登录过期事件', async () => {
    const listener = vi.fn()
    window.addEventListener(AUTH_EXPIRED_EVENT, listener)
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ error: { code: 'UNAUTHORIZED', message: '登录已过期' } }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      }),
    )

    await expect(apiFetch('/api/conversations')).rejects.toThrow('登录已过期')

    expect(listener).toHaveBeenCalledTimes(1)
    window.removeEventListener(AUTH_EXPIRED_EVENT, listener)
  })
})
