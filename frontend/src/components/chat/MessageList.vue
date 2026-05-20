<!-- 模块说明：前端 Vue 组件模块，封装页面可复用的 UI 与交互片段。 -->
<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import ChatMessage from '@/components/chat/ChatMessage.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import { MessageSquareText } from 'lucide-vue-next'
import type { Message } from '@/types/domain'

const props = defineProps<{
  messages: Message[]
  hasMore: boolean
  isLoadingOlder: boolean
  loadOlderMessages: () => Promise<void>
}>()

const scrollContainer = ref<HTMLElement | null>(null)
const isRestoringScrollPosition = ref(false)
const shouldStickToBottom = ref(true)

/** 函数作用：判断用户当前是否接近消息底部；输入参数：无；输出参数：是否接近底部。 */
function isNearBottom() {
  const container = scrollContainer.value
  if (!container) {
    return true
  }

  return container.scrollHeight - container.scrollTop - container.clientHeight < 96
}

/** 函数作用：等待 DOM 更新后滚动到消息列表底部；输入参数：无；输出参数：Promise<void>。 */
async function scrollToBottom() {
  await nextTick()

  if (!scrollContainer.value) {
    return
  }

  scrollContainer.value.scrollTop = scrollContainer.value.scrollHeight
}

/** 函数作用：加载更早消息并保持当前可视位置；输入参数：无；输出参数：Promise<void>。 */
async function loadOlderMessagesFromTop() {
  const container = scrollContainer.value
  if (!container || !props.hasMore || props.isLoadingOlder) {
    return
  }

  const previousScrollHeight = container.scrollHeight
  isRestoringScrollPosition.value = true

  try {
    await props.loadOlderMessages()
    await nextTick()
    container.scrollTop += container.scrollHeight - previousScrollHeight
  } finally {
    isRestoringScrollPosition.value = false
  }
}

/** 函数作用：处理消息列表滚动，靠近顶部时按需加载上一页；输入参数：无；输出参数：无返回值。 */
function handleScroll() {
  shouldStickToBottom.value = isNearBottom()

  if (scrollContainer.value && scrollContainer.value.scrollTop < 64) {
    void loadOlderMessagesFromTop()
  }
}

// 监听消息数量、内容长度、处理状态和消息状态，覆盖新增消息与流式 delta 更新两类场景。
watch(
  () =>
    props.messages
      .map((message) => `${message.id}:${message.content.length}:${message.processingText?.length ?? 0}:${message.status}`)
      .join('|'),
  () => {
    if (isRestoringScrollPosition.value || !shouldStickToBottom.value) {
      return
    }

    void scrollToBottom()
  },
  { immediate: true },
)
</script>

<template>
  <div
    ref="scrollContainer"
    class="min-h-0 flex-1 overflow-y-auto bg-zinc-50"
    @scroll="handleScroll"
  >
    <div v-if="messages.length === 0" class="flex min-h-full items-center justify-center">
      <EmptyState title="开始一次对话" description="发送消息后，助手会用真实流式响应逐段回复。">
        <template #icon>
          <MessageSquareText class="size-6" />
        </template>
      </EmptyState>
    </div>

    <div v-else class="space-y-5 p-4 sm:p-6">
      <div v-if="isLoadingOlder" class="py-1 text-center text-xs text-zinc-400">正在加载更早消息...</div>
      <ChatMessage v-for="message in messages" :key="message.id" :message="message" />
    </div>
  </div>
</template>
