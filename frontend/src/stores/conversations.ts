// 模块说明：前端 Pinia 状态模块，集中管理跨组件共享状态和异步动作。
import { defineStore } from 'pinia'
import { conversationsApi } from '@/api'
import type { Conversation } from '@/types/domain'

/**
 * 函数作用：按更新时间倒序排序会话，保证侧栏最新会话在前。
 * 输入参数：conversations - 会话数组。
 * 输出参数：返回排序后的新数组。
 */
function sortConversations(conversations: Conversation[]) {
  return [...conversations].sort(
    (left, right) => new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime(),
  )
}

// 会话 store 保存侧栏列表和当前会话，数据统一来自真实后端 API。
export const useConversationsStore = defineStore('conversations', {
  state: () => ({
    // 会话列表由后端加载；没有历史时保持空列表，不创建空会话。
    items: [] as Conversation[],
    // 当前活动会话 ID；允许为 null，用于“新建但未发送”的草稿态。
    activeConversationId: null as string | null,
    // 会话列表加载状态，后续真实 API 请求也会复用。
    isLoading: false,
    // 会话操作错误，侧栏或页面可以选择展示。
    errorMessage: '',
  }),
  getters: {
    // 根据 activeConversationId 找到当前会话，页面标题和侧栏高亮会使用。
    activeConversation: (state) =>
      state.items.find((conversation) => conversation.id === state.activeConversationId) ?? null,
  },
  actions: {
    /** 函数作用：从后端 API 加载会话列表；输入参数：无；输出参数：Promise<void>。 */
    async loadConversations() {
      this.isLoading = true
      this.errorMessage = ''

      try {
        const response = await conversationsApi.list()
        this.items = sortConversations(response.conversations)

        if (this.activeConversationId && !this.items.some((item) => item.id === this.activeConversationId)) {
          this.activeConversationId = null
        }

        if (!this.activeConversationId && this.items.length > 0) {
          this.activeConversationId = this.items[0]?.id ?? null
        }
      } catch (error) {
        this.errorMessage = error instanceof Error ? error.message : '加载会话失败'
      } finally {
        this.isLoading = false
      }
    },
    /** 函数作用：创建新会话并设为当前会话；输入参数：title 可选标题；输出参数：Promise<Conversation>。 */
    async createConversation(title = '新的对话') {
      this.errorMessage = ''
      const response = await conversationsApi.create({ title })
      this.items = sortConversations([response.conversation, ...this.items])
      this.activeConversationId = response.conversation.id
      return response.conversation
    },
    /** 函数作用：设置当前活动会话；输入参数：conversationId 会话 ID 或 null；输出参数：无返回值。 */
    setActiveConversation(conversationId: string | null) {
      this.activeConversationId = conversationId
    },
    /** 函数作用：切换当前会话，必要时从后端 API 补齐会话详情；输入参数：conversationId 会话 ID；输出参数：Promise<void>。 */
    async selectConversation(conversationId: string) {
      this.errorMessage = ''

      if (this.items.some((item) => item.id === conversationId)) {
        this.activeConversationId = conversationId
        return
      }

      try {
        const response = await conversationsApi.get(conversationId)
        this.items = sortConversations([response.conversation, ...this.items])
        this.activeConversationId = conversationId
      } catch (error) {
        this.errorMessage = error instanceof Error ? error.message : '切换会话失败'
        throw error
      }
    },
    /** 函数作用：硬删除会话并返回新的活动会话 ID；输入参数：conversationId 会话 ID；输出参数：Promise<string | null>。 */
    async deleteConversation(conversationId: string) {
      this.errorMessage = ''

      try {
        await conversationsApi.delete(conversationId)
        this.items = this.items.filter((item) => item.id !== conversationId)

        if (this.activeConversationId === conversationId) {
          this.activeConversationId = this.items[0]?.id ?? null
        }

        return this.activeConversationId
      } catch (error) {
        this.errorMessage = error instanceof Error ? error.message : '删除会话失败'
        throw error
      }
    },
    /** 函数作用：用第一条用户消息生成会话标题；输入参数：conversationId 会话 ID、content 用户消息；输出参数：无返回值。 */
    updateTitleFromFirstMessage(conversationId: string, content: string) {
      const conversation = this.items.find((item) => item.id === conversationId)

      if (!conversation || conversation.title !== '新的对话') {
        return
      }

      // 只在默认标题时生成一次，避免后续消息覆盖用户已经看到的会话标题。
      const normalizedContent = content.trim().replace(/\s+/g, ' ')
      conversation.title =
        normalizedContent.length > 24 ? `${normalizedContent.slice(0, 24)}...` : normalizedContent
      conversation.updatedAt = new Date().toISOString()
      this.items = sortConversations(this.items)
    },
    /** 函数作用：刷新会话更新时间并重新排序；输入参数：conversationId 会话 ID；输出参数：无返回值。 */
    touchConversation(conversationId: string) {
      const conversation = this.items.find((item) => item.id === conversationId)

      if (!conversation) {
        return
      }

      conversation.updatedAt = new Date().toISOString()
      this.items = sortConversations(this.items)
    },
  },
})
