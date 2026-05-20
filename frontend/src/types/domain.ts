// 模块说明：前端类型模块，定义领域对象、请求响应和流式事件契约。
// 消息角色与后端契约保持一致，后续工具调用和系统提示也会复用。
export type MessageRole = 'system' | 'user' | 'assistant' | 'tool'

// 消息状态用于前端展示流式生成、完成和错误三种阶段。
export type MessageStatus = 'complete' | 'streaming' | 'error'

// 长期记忆来源，主要由用户手动维护。
export type LongTermMemorySource = 'manual' | 'assistant' | 'imported'

// 联网搜索来源，用于助手消息中的引用胶囊和 hover 来源卡片。
export interface CitationSource {
  id: string
  title: string
  url: string
  domain?: string
  snippet?: string
  source?: string
}

// 引用胶囊分组，同一观点可绑定一个或多个来源。
export interface CitationGroup {
  id: string
  label: string
  sourceIds: string[]
}

// 聊天消息图片，当前以 Base64 data URL 保存并展示缩略图。
export interface MessageImage {
  name: string
  mimeType: string
  size: number
  dataUrl: string
  source?: 'uploaded' | 'generated'
  generation?: {
    intent?: string
    model?: string
    requestedQuality?: string
    quality?: string
    requestedSize?: string
    size?: string
    requestedOutputFormat?: string
    outputFormat?: string
    background?: string
    prompt?: string
    revisedPrompt?: string
    createdFrom?: string
  }
}

// 当前登录用户的前端领域模型，第一阶段只保留展示和隔离所需字段。
export interface User {
  id: string
  email: string
  displayName: string
}

// 会话列表项，标题由第一条用户消息截断生成。
export interface Conversation {
  id: string
  title: string
  // 创建时间用于后续后端排序和详情展示；部分历史响应没有该字段时可兼容。
  createdAt?: string
  updatedAt: string
}

// 聊天消息模型，status、toolName 和 processingText 主要服务前端展示状态。
export interface Message {
  id: string
  conversationId: string
  role: MessageRole
  content: string
  createdAt: string
  status?: MessageStatus
  toolName?: string
  processingText?: string
  images?: MessageImage[]
  sources?: CitationSource[]
  citationGroups?: CitationGroup[]
}

// 长期记忆模型，字段命名保持前端 camelCase，API 层负责和后端 snake_case 对齐。
export interface LongTermMemory {
  id: string
  title: string
  memoryKey: string
  content: string
  source: LongTermMemorySource
  createdAt: string
  updatedAt: string
}
