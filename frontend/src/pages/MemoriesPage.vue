<!-- 模块说明：前端页面模块，承接路由页面的状态组织和用户操作。 -->
<script setup lang="ts">
import { Brain, ShieldAlert } from 'lucide-vue-next'
import { storeToRefs } from 'pinia'
import { onMounted, ref } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import ErrorState from '@/components/base/ErrorState.vue'
import MemoryForm from '@/components/memories/MemoryForm.vue'
import MemoryList from '@/components/memories/MemoryList.vue'
import { useMemoriesStore } from '@/stores/memories'
import type { CreateMemoryRequest, UpdateMemoryRequest } from '@/types/api'
import type { LongTermMemory } from '@/types/domain'

const memoriesStore = useMemoriesStore()
// 页面直接订阅 store 状态，便于新增、编辑、删除后自动刷新 UI。
const { errorMessage, isLoading, isSaving, items } = storeToRefs(memoriesStore)

const isFormOpen = ref(false)
const editingMemory = ref<LongTermMemory | null>(null)

/** 函数作用：打开新增表单；输入参数：无；输出参数：无返回值。 */
function openCreateForm() {
  memoriesStore.clearError()
  editingMemory.value = null
  isFormOpen.value = true
}

/** 函数作用：打开编辑表单；输入参数：memory 待编辑长期记忆；输出参数：无返回值。 */
function openEditForm(memory: LongTermMemory) {
  memoriesStore.clearError()
  editingMemory.value = memory
  isFormOpen.value = true
}

/** 函数作用：关闭表单并清理编辑对象；输入参数：无；输出参数：无返回值。 */
function closeForm() {
  isFormOpen.value = false
  editingMemory.value = null
}

/** 函数作用：保存新增或编辑的长期记忆；输入参数：payload 表单数据；输出参数：Promise<void>。 */
async function handleSubmit(payload: CreateMemoryRequest | UpdateMemoryRequest) {
  if (editingMemory.value) {
    await memoriesStore.updateMemory(editingMemory.value.id, payload)
  } else {
    await memoriesStore.createMemory(payload)
  }

  closeForm()
}

/** 函数作用：二次确认后删除长期记忆；输入参数：memory 待删除记忆；输出参数：Promise<void>。 */
async function handleDelete(memory: LongTermMemory) {
  const confirmed = window.confirm(`确认删除长期记忆「${memory.title}」吗？`)

  if (!confirmed) {
    return
  }

  await memoriesStore.deleteMemory(memory.id)
}

onMounted(() => {
  void memoriesStore.loadMemories()
})
</script>

<template>
  <main class="min-h-[calc(100vh-3.5rem)] px-4 py-6 sm:px-6">
    <section class="mx-auto w-full max-w-5xl">
      <div class="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 class="text-lg font-semibold">长期记忆</h1>
          <p class="mt-1 text-sm text-zinc-500">查看、手动新增、编辑和删除长期记忆。</p>
        </div>
        <BaseButton variant="primary" @click="openCreateForm">新增记忆</BaseButton>
      </div>

      <!-- 隐私提示固定展示，提醒用户不要把敏感凭据写入长期记忆。 -->
      <div class="mb-4 flex gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
        <ShieldAlert class="mt-0.5 size-5 shrink-0" />
        <p class="leading-6">不要保存密码、密钥、验证码、银行卡号等敏感凭据。长期记忆适合保存稳定偏好和背景信息。</p>
      </div>

      <ErrorState v-if="errorMessage" class="mb-4" title="操作失败" :message="errorMessage" />

      <MemoryForm
        v-if="isFormOpen"
        class="mb-4"
        :memory="editingMemory"
        :is-saving="isSaving"
        @cancel="closeForm"
        @submit="handleSubmit"
      />

      <section v-if="isLoading" class="rounded-lg border border-zinc-200 bg-white p-6 text-sm text-zinc-500">
        正在加载长期记忆...
      </section>

      <section v-else-if="items.length === 0" class="rounded-lg border border-zinc-200 bg-white">
        <EmptyState
          title="还没有长期记忆"
          description="新增一条长期记忆后，这里会展示 title、memory_key、content、source 和时间信息。"
        >
          <template #icon>
            <Brain class="size-6" />
          </template>
          <BaseButton variant="primary" @click="openCreateForm">新增第一条记忆</BaseButton>
        </EmptyState>
      </section>

      <MemoryList v-else :memories="items" @edit="openEditForm" @delete="handleDelete" />
    </section>
  </main>
</template>
