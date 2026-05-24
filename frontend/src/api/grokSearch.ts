// 模块说明：前端 API 模块，封装独立 Grok 搜索请求。
import { apiFetch } from '@/api/http'
import type { GrokSearchRequest, GrokSearchResponse } from '@/types/api'

// Grok 搜索 API：只调用独立搜索接口，不进入普通聊天流。
export const grokSearchApi = {
  search(request: GrokSearchRequest) {
    return apiFetch<GrokSearchResponse>('/api/grok-search', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  },
}
