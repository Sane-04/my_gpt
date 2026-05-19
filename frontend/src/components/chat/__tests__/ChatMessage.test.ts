// 模块说明：前端 Vue 组件模块，封装页面可复用的 UI 与交互片段。
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ChatMessage from '@/components/chat/ChatMessage.vue'
import type { Message } from '@/types/domain'

describe('ChatMessage', () => {
  it('助手消息处理工具时展示处理状态', () => {
    const message: Message = {
      id: 'assistant-1',
      conversationId: 'conversation-1',
      role: 'assistant',
      content: '最终回答',
      processingText: '正在处理...',
      createdAt: new Date().toISOString(),
      status: 'streaming',
    }

    const wrapper = mount(ChatMessage, {
      props: {
        message,
      },
    })

    expect(wrapper.text()).toContain('正在处理...')
    expect(wrapper.text()).toContain('最终回答')
  })
})
