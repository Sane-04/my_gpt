// 模块说明：前端应用入口，初始化 Vue、Pinia、Router 和本地登录态。
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { AUTH_EXPIRED_EVENT } from './api/http'
import { useAuthStore } from './stores/auth'
import 'highlight.js/styles/github.css'
import 'katex/dist/katex.min.css'
import './styles/main.css'

// 创建单例 Pinia，先恢复登录态，再挂载路由，确保守卫读取到最新 auth 状态。
const pinia = createPinia()

// 应用启动时从 localStorage 恢复真实登录态，会自动清理过期或损坏的 session。
useAuthStore(pinia).restoreSession()

window.addEventListener(AUTH_EXPIRED_EVENT, () => {
  const authStore = useAuthStore(pinia)
  authStore.logout()

  const currentRoute = router.currentRoute.value
  if (currentRoute.name === 'login') {
    return
  }

  void router.replace({
    name: 'login',
    query: {
      redirect: currentRoute.fullPath,
    },
  })
})

createApp(App).use(pinia).use(router).mount('#app')

// 生产环境注册 PWA Service Worker，让手机可以把站点安装到主屏幕。
if (import.meta.env.PROD && 'serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    void navigator.serviceWorker.register('/sw.js')
  })
}
