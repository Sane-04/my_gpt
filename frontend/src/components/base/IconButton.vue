<!-- 模块说明：前端 Vue 组件模块，封装页面可复用的 UI 与交互片段。 -->
<script setup lang="ts">
// 图标按钮要求传入 label，同时用于 aria-label 和 title，保证可访问性。
withDefaults(
  defineProps<{
    label: string
    type?: 'button' | 'submit' | 'reset'
    disabled?: boolean
  }>(),
  {
    type: 'button',
    disabled: false,
  },
)
</script>

<template>
  <button
    :type="type"
    :aria-label="label"
    :title="label"
    :disabled="disabled"
    class="inline-flex size-10 items-center justify-center rounded-md text-zinc-600 transition hover:bg-zinc-100 hover:text-zinc-950 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800 dark:hover:text-zinc-50 dark:focus-visible:outline-zinc-100"
  >
    <slot />
  </button>
</template>
