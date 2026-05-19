// 模块说明：前端 Pinia 状态模块，集中管理跨组件共享状态和异步动作。
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { memoriesApi } from '@/api'
import { useMemoriesStore } from '@/stores/memories'
import type { LongTermMemory } from '@/types/domain'

function buildMemory(id: string, title: string, memoryKey: string, content: string): LongTermMemory {
  return {
    id,
    title,
    memoryKey,
    content,
    source: 'manual',
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  }
}

describe('useMemoriesStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('可以新增、编辑和删除长期记忆', async () => {
    const createdMemory = buildMemory('memory-1', '工作偏好', 'work_preferences', '喜欢简洁的中文说明。')
    const updatedMemory = buildMemory('memory-1', '沟通偏好', 'communication_preferences', '希望回答包含验证结果。')
    vi.spyOn(memoriesApi, 'create').mockResolvedValue({ memory: createdMemory })
    vi.spyOn(memoriesApi, 'update').mockResolvedValue({ memory: updatedMemory })
    vi.spyOn(memoriesApi, 'delete').mockResolvedValue({ deleted_id: 'memory-1' })
    const memoriesStore = useMemoriesStore()

    await memoriesStore.createMemory({
      title: '工作偏好',
      memory_key: 'work_preferences',
      content: '喜欢简洁的中文说明。',
      source: 'manual',
    })

    expect(memoriesStore.items).toHaveLength(1)

    const memory = memoriesStore.items[0]
    await memoriesStore.updateMemory(memory.id, {
      title: '沟通偏好',
      memory_key: 'communication_preferences',
      content: '希望回答包含验证结果。',
      source: 'manual',
    })

    expect(memoriesStore.items[0]?.title).toBe('沟通偏好')

    await memoriesStore.deleteMemory(memory.id)
    expect(memoriesStore.items).toHaveLength(0)
  })
})
