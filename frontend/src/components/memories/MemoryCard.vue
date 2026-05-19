<!-- 模块说明：前端 Vue 组件模块，封装页面可复用的 UI 与交互片段。 -->
<script setup lang="ts">
import { Pencil, Trash2 } from 'lucide-vue-next'
import IconButton from '@/components/base/IconButton.vue'
import type { LongTermMemory } from '@/types/domain'

defineProps<{
  memory: LongTermMemory
}>()

defineEmits<{
  edit: [memory: LongTermMemory]
  delete: [memory: LongTermMemory]
}>()

/**
 * 函数作用：格式化展示时间。
 * 输入参数：value - ISO 时间字符串。
 * 输出参数：返回本地化时间文本。
 */
function formatDate(value: string) {
  return new Date(value).toLocaleString()
}

/**
 * 函数作用：把来源枚举转换为中文展示。
 * 输入参数：source - 长期记忆来源。
 * 输出参数：返回中文来源名称。
 */
function getSourceLabel(source: LongTermMemory['source']) {
  const labels: Record<LongTermMemory['source'], string> = {
    manual: '手动',
    assistant: '助手',
    imported: '导入',
  }

  return labels[source]
}
</script>

<template>
  <article class="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm">
    <div class="flex items-start justify-between gap-3">
      <div class="min-w-0">
        <h2 class="truncate text-base font-semibold text-zinc-950">{{ memory.title }}</h2>
        <div class="mt-1 flex flex-wrap gap-2 text-xs text-zinc-500">
          <span class="rounded-md bg-zinc-100 px-2 py-1 font-mono">{{ memory.memoryKey }}</span>
          <span class="rounded-md bg-zinc-100 px-2 py-1">{{ getSourceLabel(memory.source) }}</span>
        </div>
      </div>

      <div class="flex shrink-0 items-center gap-1">
        <IconButton class="size-8" label="编辑记忆" @click="$emit('edit', memory)">
          <Pencil class="size-4" />
        </IconButton>
        <IconButton class="size-8" label="删除记忆" @click="$emit('delete', memory)">
          <Trash2 class="size-4" />
        </IconButton>
      </div>
    </div>

    <p class="mt-4 whitespace-pre-wrap break-words text-sm leading-6 text-zinc-700">
      {{ memory.content }}
    </p>

    <div class="mt-4 grid gap-1 border-t border-zinc-100 pt-3 text-xs text-zinc-500 sm:grid-cols-2">
      <span>创建：{{ formatDate(memory.createdAt) }}</span>
      <span>更新：{{ formatDate(memory.updatedAt) }}</span>
    </div>
  </article>
</template>
