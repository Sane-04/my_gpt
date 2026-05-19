<!-- 模块说明：前端 Vue 组件模块，封装页面可复用的 UI 与交互片段。 -->
<script setup lang="ts">
import MemoryCard from '@/components/memories/MemoryCard.vue'
import type { LongTermMemory } from '@/types/domain'

defineProps<{
  memories: LongTermMemory[]
}>()

defineEmits<{
  edit: [memory: LongTermMemory]
  delete: [memory: LongTermMemory]
}>()
</script>

<template>
  <!-- 列表组件只负责排列和转发操作事件，业务状态留在页面和 store。 -->
  <div class="grid gap-3">
    <MemoryCard
      v-for="memory in memories"
      :key="memory.id"
      :memory="memory"
      @edit="$emit('edit', $event)"
      @delete="$emit('delete', $event)"
    />
  </div>
</template>
