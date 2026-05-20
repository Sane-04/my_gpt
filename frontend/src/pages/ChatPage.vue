<!-- 模块说明：前端页面模块，承接路由页面的状态组织和用户操作。 -->
<script setup lang="ts">
import { Menu } from 'lucide-vue-next'
import { storeToRefs } from 'pinia'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import IconButton from '@/components/base/IconButton.vue'
import ErrorState from '@/components/base/ErrorState.vue'
import MessageComposer from '@/components/chat/MessageComposer.vue'
import MessageList from '@/components/chat/MessageList.vue'
import { useConversationsStore } from '@/stores/conversations'
import { useMessagesStore } from '@/stores/messages'
import { useUiStore } from '@/stores/ui'
import type { ChatImageInput } from '@/types/chat'

const route = useRoute()
const router = useRouter()
const uiStore = useUiStore()
const conversationsStore = useConversationsStore()
const messagesStore = useMessagesStore()
const { errorMessage, isStreaming } = storeToRefs(messagesStore)
const skipNextMessageLoadConversationId = ref<string | null>(null)

// 只使用路由中的 conversationId；没有参数表示本地草稿态，不读取或创建历史会话。
const conversationId = computed(() => {
  const routeId = route.params.conversationId
  return typeof routeId === 'string' ? routeId : null
})

// 消息列表始终从 store 读取，后续会话历史接入时页面无需改结构。
const messages = computed(() => {
  if (!conversationId.value) {
    return []
  }

  return messagesStore.getMessagesByConversationId(conversationId.value)
})

// 当前会话的消息分页状态，用于控制向上滚动时是否继续加载历史。
const messagePagination = computed(() => {
  if (!conversationId.value) {
    return { hasMore: false, isLoadingOlder: false }
  }

  return messagesStore.getPaginationByConversationId(conversationId.value)
})

// 路由变化时同步当前会话，保证侧栏高亮和页面标题一致。
watch(
  conversationId,
  async (nextConversationId) => {
    if (!nextConversationId) {
      conversationsStore.setActiveConversation(null)
      return
    }

    try {
      await conversationsStore.selectConversation(nextConversationId)

      if (skipNextMessageLoadConversationId.value === nextConversationId) {
        skipNextMessageLoadConversationId.value = null
        return
      }

      await messagesStore.loadMessages(nextConversationId)
    } catch {
      const conversation = await conversationsStore.createConversation()
      await router.replace(`/chat/${conversation.id}`)
    }
  },
)

/** 函数作用：发送当前会话消息；输入参数：content 用户输入内容；输出参数：Promise<void>。 */
async function handleSend(content: string, enableWebSearch: boolean, images: ChatImageInput[]) {
  let nextConversationId = conversationId.value

  if (!nextConversationId) {
    const conversation = await conversationsStore.createConversation()
    nextConversationId = conversation.id
    skipNextMessageLoadConversationId.value = conversation.id
    await router.replace(`/chat/${conversation.id}`)
  }

  await messagesStore.sendMessage({
    conversationId: nextConversationId,
    content,
    enableWebSearch,
    images,
  })
}

/** 函数作用：加载当前会话更早的消息页；输入参数：无；输出参数：Promise<void>。 */
async function handleLoadOlderMessages() {
  if (!conversationId.value) {
    return
  }

  await messagesStore.loadOlderMessages(conversationId.value)
}

/** 函数作用：进入聊天页时加载历史或保持空白草稿态；输入参数：无；输出参数：Promise<void>。 */
async function initializeChatPage() {
  await conversationsStore.loadConversations()

  if (conversationId.value) {
    await conversationsStore.selectConversation(conversationId.value)
    await messagesStore.loadMessages(conversationId.value)
    return
  }

  conversationsStore.setActiveConversation(null)
}

onMounted(() => {
  void initializeChatPage()
})
</script>

<template>
  <main class="relative flex h-screen min-h-0 flex-col overflow-hidden">
    <IconButton
      class="absolute left-3 top-3 z-20 bg-white/90 shadow-sm dark:bg-zinc-950/90 lg:hidden"
      label="打开侧栏"
      @click="uiStore.openSidebar()"
    >
      <Menu class="size-5" />
    </IconButton>
    <section class="mx-auto flex min-h-0 w-full max-w-7xl flex-1 flex-col px-3 pt-3 sm:px-5">
      <!-- 错误状态保留在消息区上方，不打断用户继续输入。 -->
      <ErrorState v-if="errorMessage" class="mb-4 shrink-0" title="生成失败" :message="errorMessage" />

      <!-- 消息列表负责自动滚动，输入区负责发送和停止生成。 -->
      <MessageList
        class="min-h-0 flex-1"
        :messages="messages"
        :has-more="messagePagination.hasMore"
        :is-loading-older="messagePagination.isLoadingOlder"
        :load-older-messages="handleLoadOlderMessages"
      />

      <div class="sticky bottom-0 shrink-0 bg-zinc-50 pt-4 pb-[calc(1rem+var(--app-safe-area-bottom))] dark:bg-zinc-900">
        <MessageComposer :is-streaming="isStreaming" @send="handleSend" @stop="messagesStore.stopStreaming()" />
      </div>
    </section>
  </main>
</template>
