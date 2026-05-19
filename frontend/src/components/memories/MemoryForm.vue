<!-- 模块说明：前端 Vue 组件模块，封装页面可复用的 UI 与交互片段。 -->
<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import BaseTextarea from '@/components/base/BaseTextarea.vue'
import type { CreateMemoryRequest, UpdateMemoryRequest } from '@/types/api'
import type { LongTermMemory, LongTermMemorySource } from '@/types/domain'

const props = defineProps<{
  memory?: LongTermMemory | null
  isSaving: boolean
}>()

const emit = defineEmits<{
  cancel: []
  submit: [payload: CreateMemoryRequest | UpdateMemoryRequest]
}>()

// 表单状态与领域模型分离，方便新增和编辑共用同一个组件。
const formState = reactive({
  title: '',
  memoryKey: '',
  content: '',
  source: 'manual' as LongTermMemorySource,
})

const formTitle = computed(() => (props.memory ? '编辑长期记忆' : '新增长期记忆'))
const submitText = computed(() => (props.memory ? '保存修改' : '保存记忆'))

// 切换编辑对象时回填表单；新增时清空内容并默认手动来源。
watch(
  () => props.memory,
  (memory) => {
    formState.title = memory?.title ?? ''
    formState.memoryKey = memory?.memoryKey ?? ''
    formState.content = memory?.content ?? ''
    formState.source = memory?.source ?? 'manual'
  },
  { immediate: true },
)

/** 函数作用：提交新增或编辑表单；输入参数：无；输出参数：无返回值。 */
function handleSubmit() {
  emit('submit', {
    title: formState.title,
    memory_key: formState.memoryKey,
    content: formState.content,
    source: formState.source,
  })
}
</script>

<template>
  <form class="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm" @submit.prevent="handleSubmit">
    <div class="mb-4">
      <h2 class="text-base font-semibold text-zinc-950">{{ formTitle }}</h2>
      <p class="mt-1 text-sm leading-6 text-zinc-500">长期记忆允许手动编辑，保存前请确认内容准确。</p>
    </div>

    <div class="grid gap-4">
      <BaseInput
        v-model="formState.title"
        label="标题"
        placeholder="例如：我的工作偏好"
        required
        :disabled="isSaving"
      />
      <BaseInput
        v-model="formState.memoryKey"
        label="memory_key"
        placeholder="例如：work_preferences"
        required
        :disabled="isSaving"
      />

      <label class="block">
        <span class="mb-2 block text-sm font-medium text-zinc-700">来源</span>
        <select
          v-model="formState.source"
          class="h-10 w-full rounded-md border border-zinc-200 bg-white px-3 text-sm text-zinc-950 outline-none transition focus:border-zinc-400 focus:ring-2 focus:ring-zinc-100"
          :disabled="isSaving"
        >
          <option value="manual">手动</option>
          <option value="assistant">助手</option>
          <option value="imported">导入</option>
        </select>
      </label>

      <BaseTextarea
        v-model="formState.content"
        label="内容"
        placeholder="写入需要长期保留的事实、偏好或背景信息"
        required
        :disabled="isSaving"
      />
    </div>

    <div class="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
      <BaseButton variant="secondary" :disabled="isSaving" @click="emit('cancel')">取消</BaseButton>
      <BaseButton variant="primary" type="submit" :disabled="isSaving">
        {{ isSaving ? '保存中' : submitText }}
      </BaseButton>
    </div>
  </form>
</template>
