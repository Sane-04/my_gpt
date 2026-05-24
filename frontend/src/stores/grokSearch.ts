// 模块说明：前端 Pinia 状态模块，管理独立 Grok 搜索页面状态。
import { defineStore } from 'pinia'
import { grokSearchApi } from '@/api'
import type { GrokSearchMode, GrokSearchSource } from '@/types/api'

// Grok 搜索 store 只管理独立搜索，不写入聊天会话或长期记忆。
export const useGrokSearchStore = defineStore('grokSearch', {
  state: () => ({
    query: '',
    mode: 'web' as GrokSearchMode,
    answer: '',
    sources: [] as GrokSearchSource[],
    model: '',
    isLoading: false,
    errorMessage: '',
  }),
  actions: {
    /** 函数作用：清空 Grok 搜索错误；输入参数：无；输出参数：无返回值。 */
    clearError() {
      this.errorMessage = ''
    },
    /** 函数作用：执行独立 Grok 搜索；输入参数：无；输出参数：Promise<void>。 */
    async search() {
      const query = this.query.trim()
      if (!query) {
        this.errorMessage = '请输入搜索内容'
        return
      }

      this.isLoading = true
      this.errorMessage = ''

      try {
        const response = await grokSearchApi.search({
          query,
          mode: this.mode,
        })
        this.answer = response.answer
        this.sources = response.sources
        this.model = response.model
      } catch (error) {
        this.errorMessage = error instanceof Error ? error.message : 'Grok 搜索失败'
      } finally {
        this.isLoading = false
      }
    },
  },
})
