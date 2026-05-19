// 模块说明：前端 Pinia 状态模块，集中管理跨组件共享状态和异步动作。
import { defineStore } from 'pinia'
import { memoriesApi } from '@/api'
import type { CreateMemoryRequest, UpdateMemoryRequest } from '@/types/api'
import type { LongTermMemory } from '@/types/domain'

// 长期记忆 store 管理真实 API CRUD、加载状态和页面错误提示。
export const useMemoriesStore = defineStore('memories', {
  state: () => ({
    // 当前用户的长期记忆列表，统一从后端 API 加载。
    items: [] as LongTermMemory[],
    // 页面加载状态，后续真实 API 请求会复用。
    isLoading: false,
    // 新增或编辑保存状态，避免重复提交。
    isSaving: false,
    // 记忆操作错误，页面统一展示。
    errorMessage: '',
  }),
  actions: {
    /** 函数作用：清空长期记忆错误信息；输入参数：无；输出参数：无返回值。 */
    clearError() {
      this.errorMessage = ''
    },
    /** 函数作用：加载长期记忆列表；输入参数：无；输出参数：Promise<void>。 */
    async loadMemories() {
      this.isLoading = true
      this.errorMessage = ''

      try {
        const response = await memoriesApi.list()
        this.items = response.memories
      } catch (error) {
        this.errorMessage = error instanceof Error ? error.message : '加载长期记忆失败'
      } finally {
        this.isLoading = false
      }
    },
    /** 函数作用：新增长期记忆；输入参数：request 新增请求；输出参数：Promise<void>。 */
    async createMemory(request: CreateMemoryRequest) {
      this.isSaving = true
      this.errorMessage = ''

      try {
        const response = await memoriesApi.create(request)
        this.items = [response.memory, ...this.items.filter((item) => item.id !== response.memory.id)]
      } catch (error) {
        this.errorMessage = error instanceof Error ? error.message : '保存长期记忆失败'
        throw error
      } finally {
        this.isSaving = false
      }
    },
    /** 函数作用：更新长期记忆；输入参数：memoryId 记忆 ID、request 更新请求；输出参数：Promise<void>。 */
    async updateMemory(memoryId: string, request: UpdateMemoryRequest) {
      this.isSaving = true
      this.errorMessage = ''

      try {
        const response = await memoriesApi.update(memoryId, request)
        this.items = [
          response.memory,
          ...this.items.filter((item) => item.id !== response.memory.id),
        ].sort((left, right) => new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime())
      } catch (error) {
        this.errorMessage = error instanceof Error ? error.message : '更新长期记忆失败'
        throw error
      } finally {
        this.isSaving = false
      }
    },
    /** 函数作用：删除长期记忆；输入参数：memoryId 记忆 ID；输出参数：Promise<void>。 */
    async deleteMemory(memoryId: string) {
      this.errorMessage = ''

      try {
        await memoriesApi.delete(memoryId)
        this.items = this.items.filter((item) => item.id !== memoryId)
      } catch (error) {
        this.errorMessage = error instanceof Error ? error.message : '删除长期记忆失败'
        throw error
      }
    },
  },
})
