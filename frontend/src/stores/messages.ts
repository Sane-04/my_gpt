// 模块说明：前端 Pinia 状态模块，集中管理跨组件共享状态和异步动作。
import { defineStore } from 'pinia'
import { chatApi, conversationsApi } from '@/api'
import { useConversationsStore } from '@/stores/conversations'
import type { ChatStreamEvent, SendMessageInput } from '@/types/chat'
import type { Message } from '@/types/domain'

// TextDecoder 负责把 ReadableStream 的二进制块还原为按行 JSON。
const decoder = new TextDecoder()
const MESSAGE_PAGE_SIZE = 20
const MESSAGE_CACHE_CONVERSATION_LIMIT = 3

interface MessagePaginationState {
  hasMore: boolean
  isLoadingOlder: boolean
}

/**
 * 函数作用：生成前端临时消息 ID。
 * 输入参数：prefix - 消息来源前缀，例如 user 或 assistant。
 * 输出参数：返回带时间戳和随机后缀的字符串 ID。
 */
function createMessageId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

// 消息 store 管理聊天消息、流式状态、停止生成和错误提示。
export const useMessagesStore = defineStore('messages', {
  state: () => ({
    // 按 conversationId 分组，后端加载历史消息，当前流式消息在内存中增量更新。
    itemsByConversationId: {} as Record<string, Message[]>,
    // 每个会话的消息分页状态，避免一次性把超长历史全部放进前端内存。
    paginationByConversationId: {} as Record<string, MessagePaginationState>,
    // 最近使用的会话消息缓存顺序，末尾表示最近访问。
    messageCacheOrder: [] as string[],
    // 全局流式状态，第一阶段同一时间只允许一个回复生成。
    isStreaming: false,
    // 最近一次流式错误，ChatPage 会展示。
    errorMessage: '',
    // 当前流的中断控制器，用于停止生成。
    abortController: null as AbortController | null,
    // 正在生成的助手消息 ID，后续可用于更细粒度的 UI 状态。
    streamingMessageId: null as string | null,
  }),
  getters: {
    // 返回指定会话的消息列表；无消息时返回空数组，组件无需判空。
    getMessagesByConversationId: (state) => {
      return (conversationId: string) => state.itemsByConversationId[conversationId] ?? []
    },
    // 返回指定会话的分页状态；无记录时表示还没有加载过消息。
    getPaginationByConversationId: (state) => {
      return (conversationId: string) =>
        state.paginationByConversationId[conversationId] ?? { hasMore: false, isLoadingOlder: false }
    },
  },
  actions: {
    /** 函数作用：刷新会话消息缓存的最近使用顺序并执行 LRU 淘汰；输入参数：conversationId 会话 ID；输出参数：无返回值。 */
    touchMessageCache(conversationId: string) {
      this.messageCacheOrder = [
        ...this.messageCacheOrder.filter((cachedConversationId) => cachedConversationId !== conversationId),
        conversationId,
      ]

      while (this.messageCacheOrder.length > MESSAGE_CACHE_CONVERSATION_LIMIT) {
        const evictedConversationId = this.messageCacheOrder.shift()
        if (!evictedConversationId) {
          continue
        }

        delete this.itemsByConversationId[evictedConversationId]
        delete this.paginationByConversationId[evictedConversationId]
      }
    },
    /** 函数作用：确保指定会话有消息数组；输入参数：conversationId 会话 ID；输出参数：无返回值。 */
    ensureConversationMessages(conversationId: string) {
      if (!this.itemsByConversationId[conversationId]) {
        this.itemsByConversationId[conversationId] = []
      }

      this.touchMessageCache(conversationId)
    },
    /** 函数作用：向会话追加一条消息；输入参数：message 消息对象；输出参数：无返回值。 */
    appendMessage(message: Message) {
      this.ensureConversationMessages(message.conversationId)
      this.itemsByConversationId[message.conversationId].push(message)
    },
    /** 函数作用：确保指定会话有分页状态；输入参数：conversationId 会话 ID；输出参数：分页状态。 */
    ensureConversationPagination(conversationId: string) {
      if (!this.paginationByConversationId[conversationId]) {
        this.paginationByConversationId[conversationId] = { hasMore: false, isLoadingOlder: false }
      }

      return this.paginationByConversationId[conversationId]
    },
    /** 函数作用：把流式增量追加到助手消息；输入参数：conversationId、messageId、delta；输出参数：无返回值。 */
    appendAssistantDelta(conversationId: string, messageId: string, delta: string) {
      const message = this.itemsByConversationId[conversationId]?.find((item) => item.id === messageId)

      if (!message) {
        return
      }

      message.content += delta
    },
    /** 函数作用：更新助手消息处理状态文本；输入参数：conversationId、messageId、processingText；输出参数：无返回值。 */
    setAssistantProcessingText(conversationId: string, messageId: string, processingText: string) {
      const message = this.itemsByConversationId[conversationId]?.find((item) => item.id === messageId)

      if (!message) {
        return
      }

      message.processingText = processingText
    },
    /** 函数作用：更新助手消息联网引用来源；输入参数：conversationId、messageId、sources、citationGroups；输出参数：无返回值。 */
    setAssistantSources(
      conversationId: string,
      messageId: string,
      sources: Message['sources'],
      citationGroups: Message['citationGroups'],
    ) {
      const message = this.itemsByConversationId[conversationId]?.find((item) => item.id === messageId)

      if (!message) {
        return
      }

      message.sources = sources
      message.citationGroups = citationGroups
    },
    /** 函数作用：更新助手消息状态；输入参数：conversationId、messageId、status；输出参数：无返回值。 */
    markAssistantMessage(conversationId: string, messageId: string, status: Message['status']) {
      const message = this.itemsByConversationId[conversationId]?.find((item) => item.id === messageId)

      if (!message) {
        return
      }

      message.status = status
    },
    /** 函数作用：从后端 API 加载指定会话消息；输入参数：conversationId 会话 ID；输出参数：Promise<void>。 */
    async loadMessages(conversationId: string) {
      const response = await conversationsApi.getMessages(conversationId, { limit: MESSAGE_PAGE_SIZE })
      this.setConversationMessages(conversationId, response.messages)
      this.paginationByConversationId[conversationId] = {
        hasMore: response.hasMore,
        isLoadingOlder: false,
      }
      this.touchMessageCache(conversationId)
    },
    /** 函数作用：向上翻页加载更早消息；输入参数：conversationId 会话 ID；输出参数：Promise<void>。 */
    async loadOlderMessages(conversationId: string) {
      const pagination = this.ensureConversationPagination(conversationId)

      if (!pagination.hasMore || pagination.isLoadingOlder) {
        return
      }

      const currentMessages = this.itemsByConversationId[conversationId] ?? []
      const oldestMessage = currentMessages[0]
      if (!oldestMessage) {
        return
      }

      pagination.isLoadingOlder = true

      try {
        const response = await conversationsApi.getMessages(conversationId, {
          limit: MESSAGE_PAGE_SIZE,
          before: oldestMessage.createdAt,
        })
        const existingMessageIds = new Set(currentMessages.map((message) => message.id))
        const olderMessages = response.messages.filter((message) => !existingMessageIds.has(message.id))
        this.itemsByConversationId[conversationId] = [...olderMessages, ...currentMessages]
        pagination.hasMore = response.hasMore
        this.touchMessageCache(conversationId)
      } finally {
        pagination.isLoadingOlder = false
      }
    },
    /** 函数作用：覆盖指定会话的消息列表；输入参数：conversationId、messages；输出参数：无返回值。 */
    setConversationMessages(conversationId: string, messages: Message[]) {
      this.itemsByConversationId[conversationId] = messages
      this.touchMessageCache(conversationId)
    },
    /** 函数作用：删除指定会话的内存消息；输入参数：conversationId 会话 ID；输出参数：无返回值。 */
    deleteConversationMessages(conversationId: string) {
      delete this.itemsByConversationId[conversationId]
      delete this.paginationByConversationId[conversationId]
      this.messageCacheOrder = this.messageCacheOrder.filter(
        (cachedConversationId) => cachedConversationId !== conversationId,
      )
    },
    /** 函数作用：发送用户消息并消费后端 fetch stream；输入参数：input 会话 ID 与内容；输出参数：Promise<void>。 */
    async sendMessage(input: SendMessageInput) {
      const content = input.content.trim()
      const images = input.images ?? []

      if ((!content && images.length === 0) || this.isStreaming) {
        return
      }

      const conversationsStore = useConversationsStore()
      // 用户消息立即入列，让界面先反馈用户操作。
      const userMessage: Message = {
        id: createMessageId('user'),
        conversationId: input.conversationId,
        role: 'user',
        content: content || '请分析这些图片。',
        createdAt: new Date().toISOString(),
        status: 'complete',
        images,
      }
      // 助手消息先创建 streaming 占位，后续 delta 会逐段追加到 content。
      const assistantMessage: Message = {
        id: createMessageId('assistant'),
        conversationId: input.conversationId,
        role: 'assistant',
        content: '',
        createdAt: new Date().toISOString(),
        status: 'streaming',
      }

      this.errorMessage = ''
      this.abortController = new AbortController()
      this.streamingMessageId = assistantMessage.id
      this.isStreaming = true
      this.appendMessage(userMessage)
      this.appendMessage(assistantMessage)
      conversationsStore.updateTitleFromFirstMessage(input.conversationId, content || '图片消息')
      conversationsStore.touchConversation(input.conversationId)

      try {
        const stream = await chatApi.stream(
          {
            conversationId: input.conversationId,
            content,
            enableWebSearch: input.enableWebSearch ?? false,
            images,
          },
          {
            signal: this.abortController.signal,
          },
        )
        const reader = stream.getReader()
        let buffer = ''

        // 真实 fetch stream 可能把一行 JSON 拆成多块，因此用 buffer 拼接后按行解析。
        while (true) {
          const { value, done } = await reader.read()

          if (done) {
            break
          }

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() ?? ''

          for (const line of lines) {
            if (!line.trim()) {
              continue
            }

            const event = JSON.parse(line) as ChatStreamEvent

            // delta 事件只追加文本，不结束当前助手消息。
            if (event.type === 'delta' && event.delta) {
              this.appendAssistantDelta(input.conversationId, assistantMessage.id, event.delta)
            }

            if (event.type === 'tool_call_started') {
              this.setAssistantProcessingText(
                input.conversationId,
                assistantMessage.id,
                event.toolName === 'web_search' ? '正在搜索网页...' : '正在处理...',
              )
            }

            if (event.type === 'tool_call_finished') {
              this.setAssistantProcessingText(input.conversationId, assistantMessage.id, '')
            }

            if (event.type === 'sources') {
              this.setAssistantSources(input.conversationId, assistantMessage.id, event.sources ?? [], event.citationGroups ?? [])
            }

            if (event.type === 'error') {
              throw new Error(event.message ?? '流式生成失败')
            }

            if (event.type === 'done') {
              this.markAssistantMessage(input.conversationId, assistantMessage.id, 'complete')
            }
          }
        }

        // 防御性收尾：如果流关闭前没有收到 done，也把已有内容标记为完成。
        if (assistantMessage.status === 'streaming') {
          this.markAssistantMessage(input.conversationId, assistantMessage.id, 'complete')
        }
      } catch (error) {
        // 用户主动停止不作为错误，保留已经生成的文本。
        if (this.abortController?.signal.aborted) {
          this.markAssistantMessage(input.conversationId, assistantMessage.id, 'complete')
          return
        }

        this.errorMessage = error instanceof Error ? error.message : '流式生成失败'
        this.markAssistantMessage(input.conversationId, assistantMessage.id, 'error')
      } finally {
        this.isStreaming = false
        this.abortController = null
        this.streamingMessageId = null
      }
    },
    /** 函数作用：停止当前流式生成；输入参数：无；输出参数：无返回值。 */
    stopStreaming() {
      this.abortController?.abort()
      this.isStreaming = false
    },
  },
})
