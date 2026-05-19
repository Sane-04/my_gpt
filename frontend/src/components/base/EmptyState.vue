<!-- 模块说明：前端 Vue 组件模块，封装页面可复用的 UI 与交互片段。 -->
<script setup lang="ts">
// 空状态组件用于聊天、记忆等列表为空时的统一展示。
defineProps<{
  title: string
  description: string
}>()
</script>

<template>
  <div class="mx-auto flex w-full max-w-md flex-col items-center justify-center px-6 py-12 text-center">
    <div class="mb-4 flex size-12 items-center justify-center rounded-md bg-zinc-100 text-zinc-500">
      <slot name="icon" />
    </div>
    <h2 class="text-base font-semibold text-zinc-950">{{ title }}</h2>
    <p class="mt-2 text-sm leading-6 text-zinc-500">{{ description }}</p>
    <div v-if="$slots.default" class="mt-5">
      <slot />
    </div>
  </div>
</template>
