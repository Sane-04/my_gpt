// 模块说明：前端 API 模块，统一封装后端请求、错误归一化和流式响应。
import { apiStream } from '@/api/http'
import type { ChatStreamOptions, SendMessageInput } from '@/types/chat'

// 聊天 API：封装后端 NDJSON 流式生成接口。
export const chatApi = {
  stream(input: SendMessageInput, options: ChatStreamOptions = {}) {
    return apiStream('/api/chat/stream', {
      method: 'POST',
      body: JSON.stringify(input),
      signal: options.signal,
    })
  },
}
