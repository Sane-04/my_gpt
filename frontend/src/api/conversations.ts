// 模块说明：前端 API 模块，统一封装后端请求、错误归一化和流式响应。
import { apiFetch } from '@/api/http'
import type {
  ConversationDetailResponse,
  ConversationListResponse,
  ConversationMessagesResponse,
  ConversationMessagesRequest,
  CreateConversationRequest,
  DeleteConversationResponse,
} from '@/types/api'

// 会话 API：封装会话 CRUD 和指定会话消息读取。
export const conversationsApi = {
  list() {
    return apiFetch<ConversationListResponse>('/api/conversations')
  },
  create(request: CreateConversationRequest = {}) {
    return apiFetch<ConversationDetailResponse>('/api/conversations', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  },
  get(conversationId: string) {
    return apiFetch<ConversationDetailResponse>(`/api/conversations/${conversationId}`)
  },
  delete(conversationId: string) {
    return apiFetch<DeleteConversationResponse>(`/api/conversations/${conversationId}`, {
      method: 'DELETE',
    })
  },
  getMessages(conversationId: string, request: ConversationMessagesRequest = {}) {
    const params = new URLSearchParams()
    if (request.limit) {
      params.set('limit', String(request.limit))
    }
    if (request.before) {
      params.set('before', request.before)
    }

    const query = params.toString()
    const path = `/api/conversations/${conversationId}/messages${query ? `?${query}` : ''}`
    return apiFetch<ConversationMessagesResponse>(path)
  },
}
