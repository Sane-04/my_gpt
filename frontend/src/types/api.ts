// 模块说明：前端类型模块，定义领域对象、请求响应和流式事件契约。
import type { ChatStreamEvent } from '@/types/chat'
import type { Conversation, LongTermMemory, LongTermMemorySource, Message } from '@/types/domain'

// 通用错误响应结构，后端实现时应保持 code/message 方便前端展示。
export interface ApiErrorResponse {
  error: {
    code: string
    message: string
  }
}

// 创建会话请求；title 可选，默认由第一条用户消息截断生成。
export interface CreateConversationRequest {
  title?: string
}

// 会话列表响应，按 updatedAt 倒序返回。
export interface ConversationListResponse {
  conversations: Conversation[]
}

// 会话详情响应，后端可在这里扩展更多只属于单会话的数据。
export interface ConversationDetailResponse {
  conversation: Conversation
}

// 硬删除会话响应，deleted_id 用于前端确认本地状态同步对象。
export interface DeleteConversationResponse {
  deleted_id: string
}

// 指定会话的消息列表响应，消息按 createdAt 正序返回。
export interface ConversationMessagesResponse {
  messages: Message[]
  hasMore: boolean
}

// 会话消息分页请求，before 使用当前已加载最早消息的 createdAt 作为游标。
export interface ConversationMessagesRequest {
  limit?: number
  before?: string
}

// 新增长期记忆请求，memory_key 使用后端友好的 snake_case。
export interface CreateMemoryRequest {
  title: string
  memory_key: string
  content: string
  source?: LongTermMemorySource
}

// 更新长期记忆请求，当前阶段保持整条记录提交，避免局部 patch 契约过早复杂化。
export interface UpdateMemoryRequest {
  title: string
  memory_key: string
  content: string
  source?: LongTermMemorySource
}

// 长期记忆列表响应，按 updatedAt 倒序返回。
export interface MemoryListResponse {
  memories: LongTermMemory[]
}

// 单条长期记忆响应，用于创建和更新后的状态同步。
export interface MemoryDetailResponse {
  memory: LongTermMemory
}

// 删除长期记忆响应，deleted_id 用于前端确认删除对象。
export interface DeleteMemoryResponse {
  deleted_id: string
}

// Grok 搜索模式：web 使用网页搜索，x 使用 X 搜索，auto 第一版由后端映射处理。
export type GrokSearchMode = 'web' | 'x' | 'auto'

// Grok 搜索请求，独立于普通聊天请求。
export interface GrokSearchRequest {
  query: string
  mode?: GrokSearchMode
}

// Grok 搜索来源，用于结果页展示外部链接。
export interface GrokSearchSource {
  title?: string | null
  url?: string | null
  domain?: string | null
  snippet?: string | null
}

// Grok 搜索响应，包含回答正文、来源和实际模型。
export interface GrokSearchResponse {
  answer: string
  sources: GrokSearchSource[]
  model: string
}

// 流式事件显式再导出给契约文档使用，保持 delta/done/error 稳定。
export type { ChatStreamEvent }
