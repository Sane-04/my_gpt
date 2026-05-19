<!-- 模块说明：前端 Vue 组件模块，封装页面可复用的 UI 与交互片段。 -->
<script setup lang="ts">
// 错误状态组件用于表单和聊天生成错误，保持提示样式一致。
defineProps<{
  title: string
  message: string
}>()
</script>

<template>
  <div class="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm">
    <div class="font-medium text-red-900">{{ title }}</div>
    <p class="mt-1 leading-6 text-red-700">{{ message }}</p>
  </div>
</template>
