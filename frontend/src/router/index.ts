// 模块说明：前端路由模块，定义页面路径、鉴权守卫和跳转规则。
import { createRouter, createWebHistory } from 'vue-router'
import AppShell from '@/layouts/AppShell.vue'
import ChatPage from '@/pages/ChatPage.vue'
import GrokSearchPage from '@/pages/GrokSearchPage.vue'
import LoginPage from '@/pages/LoginPage.vue'
import MemoriesPage from '@/pages/MemoriesPage.vue'
import { useAuthStore } from '@/stores/auth'

// 路由表：登录页独立展示，业务页挂在 AppShell 下复用侧栏与顶部状态区。
const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      redirect: '/chat',
    },
    {
      path: '/login',
      name: 'login',
      component: LoginPage,
    },
    {
      path: '/',
      component: AppShell,
      children: [
        {
          path: 'chat/:conversationId?',
          name: 'chat',
          component: ChatPage,
          // 聊天页需要登录态，后续真实后端接口也会依赖当前用户。
          meta: {
            requiresAuth: true,
          },
        },
        {
          path: 'memories',
          name: 'memories',
          component: MemoriesPage,
          // 长期记忆按用户隔离，未登录时不允许进入。
          meta: {
            requiresAuth: true,
          },
        },
        {
          path: 'grok-search',
          name: 'grok-search',
          component: GrokSearchPage,
          // Grok 搜索使用独立后端配置，但仍按当前用户登录态访问。
          meta: {
            requiresAuth: true,
          },
        },
      ],
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/chat',
    },
  ],
})

// 全局鉴权守卫：未登录访问保护页跳登录页，已登录访问登录页回到聊天页。
router.beforeEach((to) => {
  const authStore = useAuthStore()

  if (to.name === 'login' && authStore.isAuthenticated) {
    return { name: 'chat' }
  }

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    return {
      name: 'login',
      query: {
        redirect: to.fullPath,
      },
    }
  }

  return true
})

export default router
