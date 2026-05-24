// 模块说明：前端 API 模块，统一封装后端请求、错误归一化和流式响应。
import { describe, expect, it } from 'vitest'
import { authApi, chatApi, conversationsApi, memoriesApi } from '@/api'

describe('api modules', () => {
  it('按业务域导出真实 API 函数', () => {
    expect(authApi.login).toBeTypeOf('function')
    expect(conversationsApi.list).toBeTypeOf('function')
    expect(chatApi.stream).toBeTypeOf('function')
    expect(memoriesApi.create).toBeTypeOf('function')
  })
})
