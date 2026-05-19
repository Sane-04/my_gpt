// 模块说明：前端类型模块，定义领域对象、请求响应和流式事件契约。
import type { CitationGroup, CitationSource } from '@/types/domain'

// 流式事件类型：delta 表示回答增量文本，tool_call_* 表示后端正在执行工具。
export type ChatStreamEventType = 'delta' | 'tool_call_started' | 'tool_call_finished' | 'sources' | 'done' | 'error'

// fetch stream 中每一行 JSON 对应的事件结构。
export interface ChatStreamEvent {
  type: ChatStreamEventType
  delta?: string
  message?: string
  toolName?: string
  sources?: CitationSource[]
  citationGroups?: CitationGroup[]
}

// 聊天图片输入：第一版使用 Base64 data URL 随请求发送。
export interface ChatImageInput {
  name: string
  mimeType: string
  size: number
  dataUrl: string
}

// 发送消息输入，后续真实 API Client 会复用这个契约。
export interface SendMessageInput {
  conversationId: string
  content: string
  enableWebSearch?: boolean
  images?: ChatImageInput[]
}

// 流式请求可选项，目前只需要 AbortSignal 支持停止生成。
export interface ChatStreamOptions {
  signal?: AbortSignal
}
