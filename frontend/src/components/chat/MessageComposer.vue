<!-- 模块说明：前端 Vue 组件模块，封装页面可复用的 UI 与交互片段。 -->
<script setup lang="ts">
import { ImagePlus, Search, SendHorizontal, Square, X } from 'lucide-vue-next'
import { computed, ref } from 'vue'
import IconButton from '@/components/base/IconButton.vue'
import type { ChatImageInput } from '@/types/chat'

const props = defineProps<{
  isStreaming: boolean
}>()

const emit = defineEmits<{
  send: [content: string, enableWebSearch: boolean, images: ChatImageInput[]]
  stop: []
}>()

const content = ref('')
const enableWebSearch = ref(false)
const imageInput = ref<HTMLInputElement | null>(null)
const images = ref<ChatImageInput[]>([])
const imageError = ref('')
const allowedImageTypes = new Set(['image/png', 'image/jpeg', 'image/webp', 'image/gif'])
const maxImageCount = 5
const maxImageSize = 10 * 1024 * 1024
// 只有有输入或图片，且没有流式生成时才允许发送。
const canSend = computed(() => (content.value.trim().length > 0 || images.value.length > 0) && !props.isStreaming)

/** 函数作用：把图片文件读取为 Base64 data URL；输入参数：file 图片文件；输出参数：Promise<string>。 */
function readImageAsDataUrl(file: File) {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => reject(new Error('图片读取失败'))
    reader.readAsDataURL(file)
  })
}

/** 函数作用：打开图片选择框；输入参数：无；输出参数：无返回值。 */
function openImagePicker() {
  imageInput.value?.click()
}

/** 函数作用：处理图片选择并执行前端限制校验；输入参数：event input change 事件；输出参数：Promise<void>。 */
async function addImageFiles(files: File[]) {
  imageError.value = ''

  for (const file of files) {
    if (images.value.length >= maxImageCount) {
      imageError.value = `最多上传 ${maxImageCount} 张图片`
      break
    }

    if (!allowedImageTypes.has(file.type)) {
      imageError.value = '仅支持 png、jpeg、webp、gif 图片'
      continue
    }

    if (file.size > maxImageSize) {
      imageError.value = '单张图片不能超过 10MB'
      continue
    }

    const dataUrl = await readImageAsDataUrl(file)
    images.value.push({
      name: file.name,
      mimeType: file.type,
      size: file.size,
      dataUrl,
    })
  }
}

/** 函数作用：处理图片选择并执行前端限制校验；输入参数：event input change 事件；输出参数：Promise<void>。 */
async function handleImageChange(event: Event) {
  const target = event.target
  if (!(target instanceof HTMLInputElement)) {
    return
  }

  const files = Array.from(target.files ?? [])
  target.value = ''
  await addImageFiles(files)
}

/** 函数作用：从剪贴板中提取图片并加入待发送列表；输入参数：event 剪贴板事件；输出参数：Promise<void>。 */
async function handlePaste(event: ClipboardEvent) {
  const items = Array.from(event.clipboardData?.items ?? [])
  const pastedImages = items
    .filter((item) => item.kind === 'file' && allowedImageTypes.has(item.type))
    .map((item) => item.getAsFile())
    .filter((file) => file !== null)

  if (pastedImages.length === 0) {
    return
  }

  await addImageFiles(pastedImages)
}

/** 函数作用：移除待发送图片；输入参数：index 图片索引；输出参数：无返回值。 */
function removeImage(index: number) {
  images.value.splice(index, 1)
  imageError.value = ''
}

/** 函数作用：提交当前输入内容；输入参数：无；输出参数：无返回值。 */
function handleSubmit() {
  const nextContent = content.value.trim()

  if ((!nextContent && images.value.length === 0) || props.isStreaming) {
    return
  }

  emit('send', nextContent, enableWebSearch.value, [...images.value])
  content.value = ''
  images.value = []
  imageError.value = ''
}

/** 函数作用：处理 Enter 发送、Shift+Enter 换行；输入参数：event 键盘事件；输出参数：无返回值。 */
function handleKeydown(event: KeyboardEvent) {
  if (event.key !== 'Enter' || event.shiftKey) {
    return
  }

  event.preventDefault()
  handleSubmit()
}
</script>

<template>
  <form class="rounded-2xl border border-zinc-200 bg-white px-3 py-1.5 shadow-sm dark:border-zinc-800 dark:bg-zinc-950" @submit.prevent="handleSubmit">
    <div v-if="images.length" class="mb-3 flex flex-wrap gap-2">
      <div
        v-for="(image, index) in images"
        :key="`${image.name}-${index}`"
        class="relative size-20 overflow-hidden rounded-md border border-zinc-200 bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900"
      >
        <img :src="image.dataUrl" :alt="image.name" class="size-full object-cover" />
        <button
          type="button"
          class="absolute right-1 top-1 inline-flex size-6 items-center justify-center rounded-md bg-white/90 text-zinc-700 shadow-sm transition hover:bg-white hover:text-zinc-950 dark:bg-zinc-950/90 dark:text-zinc-200 dark:hover:bg-zinc-900 dark:hover:text-white"
          :aria-label="`移除 ${image.name}`"
          @click="removeImage(index)"
        >
          <X class="size-4" />
        </button>
      </div>
    </div>
    <div v-if="imageError" class="mb-2 text-xs text-red-600">{{ imageError }}</div>
    <div class="flex items-center gap-2">
      <input
        ref="imageInput"
        type="file"
        accept="image/png,image/jpeg,image/webp,image/gif"
        multiple
        class="hidden"
        :disabled="isStreaming"
        @change="handleImageChange"
      />
      <textarea
        v-model="content"
        rows="1"
        placeholder="勇敢牛牛！"
        class="max-h-40 min-h-10 flex-1 resize-none rounded-md border-0 bg-transparent px-2 py-2.5 text-sm leading-5 text-zinc-950 outline-none placeholder:text-zinc-400 dark:text-zinc-50 dark:placeholder:text-zinc-500"
        :disabled="isStreaming"
        @keydown="handleKeydown"
        @paste="handlePaste"
      />

      <IconButton v-if="isStreaming" label="停止生成" @click="emit('stop')">
        <Square class="size-5 fill-current" />
      </IconButton>
      <template v-else>
        <IconButton label="上传图片" @click="openImagePicker">
          <ImagePlus class="size-5" />
        </IconButton>
        <IconButton
          label="联网搜索"
          :class="{ 'bg-sky-100 text-sky-700 hover:bg-sky-200 hover:text-sky-800': enableWebSearch }"
          @click="enableWebSearch = !enableWebSearch"
        >
          <Search class="size-5" />
        </IconButton>
        <IconButton label="发送消息" type="submit" :class="{ 'opacity-40': !canSend }">
          <SendHorizontal class="size-5" />
        </IconButton>
      </template>
    </div>
  </form>
</template>
