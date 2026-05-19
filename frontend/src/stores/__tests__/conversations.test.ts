// 模块说明：前端 Pinia 状态模块，集中管理跨组件共享状态和异步动作。
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { conversationsApi } from '@/api'
import { useConversationsStore } from '@/stores/conversations'
import type { Conversation } from '@/types/domain'

function buildConversation(id: string, title: string): Conversation {
  return {
    id,
    title,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  }
}

describe('useConversationsStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('无历史会话时保持空列表和空 active', async () => {
    vi.spyOn(conversationsApi, 'list').mockResolvedValue({ conversations: [] })
    const conversationsStore = useConversationsStore()

    await conversationsStore.loadConversations()

    expect(conversationsStore.items).toHaveLength(0)
    expect(conversationsStore.activeConversationId).toBeNull()
  })

  it('可以加载、新建和切换会话', async () => {
    const conversation = buildConversation('conversation-1', '测试会话')
    vi.spyOn(conversationsApi, 'list').mockResolvedValue({ conversations: [] })
    vi.spyOn(conversationsApi, 'create').mockResolvedValue({ conversation })
    const conversationsStore = useConversationsStore()

    await conversationsStore.loadConversations()
    const createdConversation = await conversationsStore.createConversation('测试会话')

    expect(conversationsStore.activeConversationId).toBe(createdConversation.id)
    expect(conversationsStore.items.some((item) => item.id === createdConversation.id)).toBe(true)

    await conversationsStore.selectConversation(createdConversation.id)
    expect(conversationsStore.activeConversation?.title).toBe('测试会话')
  })

  it('删除最后一个会话后不会自动创建空会话', async () => {
    const conversation = buildConversation('conversation-1', '待删除会话')
    vi.spyOn(conversationsApi, 'create').mockResolvedValue({ conversation })
    vi.spyOn(conversationsApi, 'delete').mockResolvedValue({ deleted_id: conversation.id })
    const conversationsStore = useConversationsStore()

    const createdConversation = await conversationsStore.createConversation('待删除会话')

    const nextConversationId = await conversationsStore.deleteConversation(createdConversation.id)

    expect(nextConversationId).toBeNull()
    expect(conversationsStore.items).toHaveLength(0)
    expect(conversationsStore.activeConversationId).toBeNull()
  })
})
