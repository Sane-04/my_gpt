// 模块说明：前端 Pinia 状态模块，集中管理跨组件共享状态和异步动作。
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { chatApi, conversationsApi } from '@/api'
import { useMessagesStore } from '@/stores/messages'
import type { Message } from '@/types/domain'

const encoder = new TextEncoder()

function createStream(events: object[]): ReadableStream<Uint8Array<ArrayBuffer>> {
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const event of events) {
        controller.enqueue(encoder.encode(`${JSON.stringify(event)}\n`) as Uint8Array<ArrayBuffer>)
      }
      controller.close()
    },
  }) as ReadableStream<Uint8Array<ArrayBuffer>>
}

function buildMessage(id: string, content: string, createdAt: string, conversationId = 'conversation-1'): Message {
  return {
    id,
    conversationId,
    role: 'user',
    content,
    createdAt,
    status: 'complete',
  }
}

describe('useMessagesStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('可以发送消息并消费真实协议 stream', async () => {
    const image = {
      name: 'cat.png',
      mimeType: 'image/png',
      size: 12,
      dataUrl: 'data:image/png;base64,aGVsbG8=',
    }
    const streamSpy = vi.spyOn(chatApi, 'stream').mockResolvedValue(
      createStream([
        { type: 'tool_call_started', toolName: 'web_search' },
        { type: 'tool_call_finished', toolName: 'web_search' },
        { type: 'delta', delta: '我已经收到你的消息。[[cite:src_1]]' },
        {
          type: 'sources',
          sources: [
            {
              id: 'src_1',
              title: 'OpenAI News',
              url: 'https://example.com/openai-news',
              domain: 'example.com',
              snippet: '模型新闻摘要',
              source: 'web',
            },
          ],
          citationGroups: [{ id: 'cite_1', label: 'OpenAI News', sourceIds: ['src_1'] }],
        },
        { type: 'done' },
      ]),
    )
    const messagesStore = useMessagesStore()
    const processingSpy = vi.spyOn(messagesStore, 'setAssistantProcessingText')

    await messagesStore.sendMessage({
      conversationId: 'conversation-1',
      content: '请给我一个 TypeScript 示例',
      enableWebSearch: true,
      images: [image],
    })

    const messages = messagesStore.getMessagesByConversationId('conversation-1')
    expect(messages).toHaveLength(2)
    expect(messages[0]?.role).toBe('user')
    expect(messages[0]?.images).toEqual([image])
    expect(messages[1]?.role).toBe('assistant')
    expect(messages[1]?.status).toBe('complete')
    expect(messages[1]?.processingText).toBe('')
    expect(messages[1]?.content).toBe('我已经收到你的消息。[[cite:src_1]]')
    expect(messages[1]?.sources?.[0]?.id).toBe('src_1')
    expect(messages[1]?.citationGroups?.[0]?.label).toBe('OpenAI News')
    expect(streamSpy).toHaveBeenCalledWith(
      {
        conversationId: 'conversation-1',
        content: '请给我一个 TypeScript 示例',
        enableWebSearch: true,
        images: [image],
      },
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
    expect(processingSpy).toHaveBeenCalledWith('conversation-1', messages[1]?.id, '正在搜索网页...')
  })

  it('默认只加载最近 20 条，并在向上翻页时前置更早消息', async () => {
    const latestMessages = Array.from({ length: 20 }, (_, index) =>
      buildMessage(`message-${index + 21}`, `最近消息 ${index + 21}`, `2026-05-18T10:${index + 20}:00.000Z`),
    )
    const olderMessages = [
      buildMessage('message-19', '更早消息 19', '2026-05-18T10:18:00.000Z'),
      buildMessage('message-20', '更早消息 20', '2026-05-18T10:19:00.000Z'),
    ]
    const getMessagesSpy = vi
      .spyOn(conversationsApi, 'getMessages')
      .mockResolvedValueOnce({ messages: latestMessages, hasMore: true })
      .mockResolvedValueOnce({ messages: olderMessages, hasMore: false })
    const messagesStore = useMessagesStore()

    await messagesStore.loadMessages('conversation-1')

    expect(getMessagesSpy).toHaveBeenCalledWith('conversation-1', { limit: 20 })
    expect(messagesStore.getMessagesByConversationId('conversation-1')).toHaveLength(20)
    expect(messagesStore.getPaginationByConversationId('conversation-1').hasMore).toBe(true)

    await messagesStore.loadOlderMessages('conversation-1')

    expect(getMessagesSpy).toHaveBeenLastCalledWith('conversation-1', {
      limit: 20,
      before: latestMessages[0]?.createdAt,
    })
    expect(messagesStore.getMessagesByConversationId('conversation-1')).toHaveLength(22)
    expect(messagesStore.getMessagesByConversationId('conversation-1')[0]?.id).toBe('message-19')
    expect(messagesStore.getPaginationByConversationId('conversation-1').hasMore).toBe(false)
  })

  it('只保留最近 3 个会话的消息缓存', async () => {
    vi.spyOn(conversationsApi, 'getMessages').mockImplementation(async (conversationId) => ({
      messages: [buildMessage(`${conversationId}-message`, conversationId, '2026-05-18T10:00:00.000Z', conversationId)],
      hasMore: true,
    }))
    const messagesStore = useMessagesStore()

    await messagesStore.loadMessages('conversation-1')
    await messagesStore.loadMessages('conversation-2')
    await messagesStore.loadMessages('conversation-3')
    await messagesStore.loadMessages('conversation-4')

    expect(messagesStore.getMessagesByConversationId('conversation-1')).toHaveLength(0)
    expect(messagesStore.getMessagesByConversationId('conversation-2')).toHaveLength(1)
    expect(messagesStore.getMessagesByConversationId('conversation-3')).toHaveLength(1)
    expect(messagesStore.getMessagesByConversationId('conversation-4')).toHaveLength(1)
    expect(messagesStore.getPaginationByConversationId('conversation-1').hasMore).toBe(false)
    expect(messagesStore.messageCacheOrder).toEqual(['conversation-2', 'conversation-3', 'conversation-4'])
  })

  it('天气工具调用时展示查询天气状态', async () => {
    vi.spyOn(chatApi, 'stream').mockResolvedValue(
      createStream([
        { type: 'tool_call_started', toolName: 'get_weather' },
        { type: 'tool_call_finished', toolName: 'get_weather' },
        { type: 'delta', delta: '菏泽今天晴朗。' },
        { type: 'done' },
      ]),
    )
    const messagesStore = useMessagesStore()
    const processingSpy = vi.spyOn(messagesStore, 'setAssistantProcessingText')

    await messagesStore.sendMessage({
      conversationId: 'conversation-1',
      content: '今天菏泽的天气怎么样？',
    })

    const messages = messagesStore.getMessagesByConversationId('conversation-1')
    expect(processingSpy).toHaveBeenCalledWith('conversation-1', messages[1]?.id, '正在查询天气...')
  })
})
