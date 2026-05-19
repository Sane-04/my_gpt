<!-- 模块说明：前端 Vue 组件模块，封装页面可复用的 UI 与交互片段。 -->
<script setup lang="ts">
import { Wrench } from 'lucide-vue-next'

// 工具提示消息用于后续展示工具调用状态，目前先提供结构占位。
defineProps<{
  toolName?: string
  content: string
}>()
</script>

<template>
  <div class="flex items-start gap-2 rounded-md border border-zinc-200 bg-zinc-50 px-3 py-2 text-sm text-zinc-600">
    <Wrench class="mt-0.5 size-4 shrink-0" />
    <div class="min-w-0">
      <div class="font-medium text-zinc-800">{{ toolName ?? '工具状态' }}</div>
      <div class="mt-1 break-words leading-6">{{ content }}</div>
    </div>
  </div>
</template>
