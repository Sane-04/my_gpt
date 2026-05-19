<!-- 模块说明：前端 Vue 组件模块，封装页面可复用的 UI 与交互片段。 -->
<script setup lang="ts">
// 基础按钮封装项目常用尺寸、状态和视觉变体，避免页面重复写 Tailwind 类。
withDefaults(
  defineProps<{
    type?: 'button' | 'submit' | 'reset'
    variant?: 'primary' | 'secondary' | 'ghost'
    disabled?: boolean
  }>(),
  {
    type: 'button',
    variant: 'secondary',
    disabled: false,
  },
)
</script>

<template>
  <button
    :type="type"
    :disabled="disabled"
    class="inline-flex h-10 items-center justify-center gap-2 rounded-md px-4 text-sm font-medium transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-900 disabled:cursor-not-allowed disabled:opacity-50"
    :class="{
      'bg-zinc-950 text-white hover:bg-zinc-800': variant === 'primary',
      'border border-zinc-200 bg-white text-zinc-800 hover:bg-zinc-100': variant === 'secondary',
      'text-zinc-700 hover:bg-zinc-100': variant === 'ghost',
    }"
  >
    <slot />
  </button>
</template>
