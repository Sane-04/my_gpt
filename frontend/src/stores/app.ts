// 模块说明：前端 Pinia 状态模块，集中管理跨组件共享状态和异步动作。
import { defineStore } from 'pinia'

// 应用级基础状态，当前只用于初始化验证，后续可放全局配置和启动状态。
export const useAppStore = defineStore('app', {
  state: () => ({
    // 应用显示名称，避免页面里散落硬编码品牌名。
    appName: 'My GPT',
    // 基础就绪标记，后续可扩展为初始化加载状态。
    isReady: true,
  }),
})
