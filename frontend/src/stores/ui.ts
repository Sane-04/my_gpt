// 模块说明：前端 Pinia 状态模块，集中管理跨组件共享状态和异步动作。
import { defineStore } from 'pinia'

// UI store 只承载跨组件界面状态，避免移动端侧栏开关散落在多个组件中。
export const useUiStore = defineStore('ui', {
  state: () => ({
    // 移动端侧栏是否打开；桌面端由 CSS 固定展示。
    isSidebarOpen: false,
  }),
  actions: {
    /** 函数作用：打开移动端侧栏；输入参数：无；输出参数：无返回值。 */
    openSidebar() {
      this.isSidebarOpen = true
    },
    /** 函数作用：关闭移动端侧栏；输入参数：无；输出参数：无返回值。 */
    closeSidebar() {
      this.isSidebarOpen = false
    },
    /** 函数作用：切换移动端侧栏显示状态；输入参数：无；输出参数：无返回值。 */
    toggleSidebar() {
      this.isSidebarOpen = !this.isSidebarOpen
    },
  },
})
