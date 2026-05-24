<!-- 模块说明：前端布局模块，组织应用外壳、导航和全局交互。 -->
<script setup lang="ts">
import { storeToRefs } from 'pinia'
import {
  Brain,
  LogOut,
  Menu,
  MessageSquarePlus,
  PanelLeftClose,
  Search,
  Trash2,
  UserCircle,
} from 'lucide-vue-next'
import { computed, onBeforeUnmount, onMounted, watch } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import IconButton from '@/components/base/IconButton.vue'
import { useAuthStore } from '@/stores/auth'
import { useConversationsStore } from '@/stores/conversations'
import { useMessagesStore } from '@/stores/messages'
import { useUiStore } from '@/stores/ui'

const route = useRoute()
const router = useRouter()
const uiStore = useUiStore()
const authStore = useAuthStore()
const conversationsStore = useConversationsStore()
const messagesStore = useMessagesStore()
const { isSidebarOpen } = storeToRefs(uiStore)
const { user } = storeToRefs(authStore)
const { activeConversation, items, activeConversationId } = storeToRefs(conversationsStore)
let mediaQuery: MediaQueryList | null = null
let syncSidebarByViewport: (() => void) | null = null

// 根据当前路由显示顶部状态区标题，保持页面切换时上下文明确。
const currentSection = computed(() => {
  if (route.name === 'grok-search') {
    return 'Grok 搜索'
  }

  if (route.name === 'memories') {
    return '长期记忆'
  }

  return activeConversation.value?.title ?? '新的对话'
})
const shouldShowHeader = computed(() => route.name !== 'chat')

// 移动端切换路由后自动收起侧栏，避免遮罩残留影响主内容操作。
watch(
  () => route.fullPath,
  () => {
    if (!mediaQuery?.matches) {
      uiStore.closeSidebar()
    }
  },
)

// 应用外壳挂载时加载后端会话列表，让刷新后侧栏立即恢复历史。
onMounted(() => {
  mediaQuery = window.matchMedia('(min-width: 1024px)')
  syncSidebarByViewport = () => {
    if (mediaQuery?.matches) {
      uiStore.openSidebar()
    } else {
      uiStore.closeSidebar()
    }
  }

  syncSidebarByViewport()
  mediaQuery.addEventListener('change', syncSidebarByViewport)
  void conversationsStore.loadConversations()
})

onBeforeUnmount(() => {
  if (syncSidebarByViewport) {
    mediaQuery?.removeEventListener('change', syncSidebarByViewport)
  }
})

/** 函数作用：进入新对话草稿态；输入参数：无；输出参数：Promise<void>。 */
async function handleCreateConversation() {
  messagesStore.stopStreaming()
  conversationsStore.setActiveConversation(null)
  await router.push('/chat')
}

/** 函数作用：二次确认后硬删除会话；输入参数：conversationId 会话 ID；输出参数：Promise<void>。 */
async function handleDeleteConversation(conversationId: string) {
  const confirmed = window.confirm('确认删除这个会话吗？该操作会同步删除会话下的消息')

  if (!confirmed) {
    return
  }

  messagesStore.stopStreaming()
  const nextConversationId = await conversationsStore.deleteConversation(conversationId)
  messagesStore.deleteConversationMessages(conversationId)

  if (nextConversationId) {
    await router.push(`/chat/${nextConversationId}`)
  } else {
    await router.push('/chat')
  }
}

/** 函数作用：退出当前登录态并返回登录页；输入参数：无；输出参数：Promise<void>。 */
async function handleLogout() {
  authStore.logout()
  await router.push('/login')
}
</script>

<template>
  <div class="min-h-screen bg-zinc-50 text-zinc-950 dark:bg-zinc-900 dark:text-zinc-50">
    <!-- 移动端侧栏遮罩，点击空白处关闭侧栏。 -->
    <div
      v-if="isSidebarOpen"
      class="fixed inset-0 z-30 bg-zinc-950/30 dark:bg-black/50 lg:hidden"
      @click="uiStore.closeSidebar()"
    />

    <!-- 应用主侧栏：桌面端固定展示，移动端由 uiStore 控制折叠。 -->
    <aside
      class="fixed inset-y-0 left-0 z-40 flex w-72 -translate-x-full flex-col border-r border-zinc-200 bg-white transition-transform duration-200 dark:border-zinc-800 dark:bg-zinc-950"
      :class="{ 'translate-x-0': isSidebarOpen }"
    >
      <div class="flex h-14 items-center justify-between border-b border-zinc-200 px-4 dark:border-zinc-800">
        <RouterLink to="/chat" class="flex items-center gap-2 text-sm font-semibold">
          <span class="size-8 overflow-hidden rounded-md bg-zinc-100 dark:bg-zinc-800">
            <img src="/cow.jpg" alt="应用头像" class="size-full object-cover" />
          </span>
          My GPT FROM SANE
        </RouterLink>
        <IconButton label="关闭侧栏" @click="uiStore.closeSidebar()">
          <PanelLeftClose class="size-5" />
        </IconButton>
      </div>

      <div class="border-b border-zinc-200 p-3 dark:border-zinc-800">
        <button
          type="button"
          class="flex h-10 w-full items-center gap-2 rounded-md bg-transparent px-3 text-sm font-medium text-zinc-800 transition hover:bg-zinc-100 dark:text-zinc-100 dark:hover:bg-zinc-800"
          @click="handleCreateConversation"
        >
          <MessageSquarePlus class="size-4" />
          新建对话
        </button>
      </div>

      <nav class="flex-1 overflow-y-auto p-3">
        <div class="mb-2 px-2 text-xs font-medium uppercase tracking-wide text-zinc-400 dark:text-zinc-500">会话</div>
        <div
          v-for="conversation in items"
          :key="conversation.id"
          class="group mb-1 flex items-center gap-1 rounded-md transition hover:bg-zinc-100 dark:hover:bg-zinc-800"
          :class="{
            'bg-zinc-100 dark:bg-zinc-800': activeConversationId === conversation.id,
          }"
        >
          <RouterLink
            :to="`/chat/${conversation.id}`"
            class="min-w-0 flex-1 truncate px-3 py-2 text-sm"
            :class="{
              'font-medium text-zinc-950 dark:text-zinc-50': activeConversationId === conversation.id,
              'text-zinc-600 dark:text-zinc-300': activeConversationId !== conversation.id,
            }"
          >
            {{ conversation.title }}
          </RouterLink>
          <IconButton
            class="mr-1 size-8 opacity-100 transition lg:opacity-0 lg:group-hover:opacity-100 lg:focus:opacity-100"
            label="删除会话"
            @click.prevent.stop="handleDeleteConversation(conversation.id)"
          >
            <Trash2 class="size-4" />
          </IconButton>
        </div>
      </nav>

      <!-- 用户状态区：展示当前登录用户并提供退出入口。 -->
      <div class="border-t border-zinc-200 p-3 dark:border-zinc-800">
        <RouterLink
          to="/grok-search"
          class="flex h-10 items-center gap-2 rounded-md px-3 text-sm transition hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
          :class="route.name === 'grok-search' ? 'bg-zinc-100 font-medium text-zinc-950 dark:bg-zinc-800 dark:text-zinc-50' : 'text-zinc-700'"
        >
          <Search class="size-4" />
          Grok 搜索
        </RouterLink>
        <RouterLink
          to="/memories"
          class="flex h-10 items-center gap-2 rounded-md px-3 text-sm transition hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
          :class="route.name === 'memories' ? 'bg-zinc-100 font-medium text-zinc-950 dark:bg-zinc-800 dark:text-zinc-50' : 'text-zinc-700'"
        >
          <Brain class="size-4" />
          长期记忆
        </RouterLink>
        <div class="mt-3 rounded-md border border-zinc-200 bg-zinc-50 p-3 dark:border-zinc-800 dark:bg-zinc-900">
          <div class="flex items-center gap-2">
            <UserCircle class="size-5 text-zinc-500 dark:text-zinc-400" />
            <div class="min-w-0">
              <div class="truncate text-sm font-medium text-zinc-800 dark:text-zinc-100">
                {{ user?.displayName ?? '未登录用户' }}
              </div>
              <div class="truncate text-xs text-zinc-500 dark:text-zinc-400">
                {{ user?.email ?? '请先登录' }}
              </div>
            </div>
          </div>
          <button
            type="button"
            class="mt-3 flex h-9 w-full items-center justify-center gap-2 rounded-md border border-zinc-200 bg-white text-sm font-medium text-zinc-700 transition hover:bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-200 dark:hover:bg-zinc-800"
            @click="handleLogout"
          >
            <LogOut class="size-4" />
            退出登录
          </button>
        </div>
      </div>
    </aside>

    <div
      class="flex h-screen min-h-0 flex-col overflow-hidden transition-[padding] duration-200"
      :class="{ 'lg:pl-72': isSidebarOpen }"
    >
      <IconButton
        v-if="!isSidebarOpen"
        class="fixed left-3 top-3 z-30 hidden bg-white/90 shadow-sm dark:bg-zinc-950/90 lg:inline-flex"
        label="打开侧栏"
        @click="uiStore.openSidebar()"
      >
        <Menu class="size-5" />
      </IconButton>

      <!-- 顶部状态栏承载移动菜单按钮和当前页面轻量状态。 -->
      <header
        v-if="shouldShowHeader"
        class="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-zinc-200 bg-white/90 px-3 backdrop-blur dark:border-zinc-800 dark:bg-zinc-950/90 sm:px-5"
      >
        <div class="flex min-w-0 items-center gap-2">
          <IconButton class="lg:hidden" label="打开侧栏" @click="uiStore.openSidebar()">
            <Menu class="size-5" />
          </IconButton>
          <div class="min-w-0">
            <div class="truncate text-sm font-semibold">{{ currentSection }}</div>
          </div>
        </div>
      </header>

      <RouterView />
    </div>
  </div>
</template>
