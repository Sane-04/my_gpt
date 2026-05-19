<!-- 模块说明：前端 Vue 组件模块，封装页面可复用的 UI 与交互片段。 -->
<script setup lang="ts">
import { ImagePlus, Mic, MicOff, Search, SendHorizontal, Square, X } from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'
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
const isListening = ref(false)
const speechError = ref('')
const interimSpeechText = ref('')
const allowedImageTypes = new Set(['image/png', 'image/jpeg', 'image/webp', 'image/gif'])
const maxImageCount = 5
const maxImageSize = 10 * 1024 * 1024
let speechRecognition: SpeechRecognition | null = null
// 只有有输入或图片，且没有流式生成时才允许发送。
const canSend = computed(() => (content.value.trim().length > 0 || images.value.length > 0) && !props.isStreaming)
const isSpeechSupported = computed(() => getSpeechRecognitionConstructor() !== null)
const speechStatusText = computed(() => {
  if (speechError.value || interimSpeechText.value) {
    return speechError.value || interimSpeechText.value
  }

  if (!isSpeechSupported.value && !props.isStreaming) {
    return '当前浏览器不支持语音输入'
  }

  return ''
})
const speechStatusClass = computed(() => (speechError.value || !isSpeechSupported.value ? 'text-red-600' : 'text-zinc-500'))

/** 函数作用：获取当前浏览器可用的语音识别构造器；输入参数：无；输出参数：语音识别构造器或 null。 */
function getSpeechRecognitionConstructor() {
  if (typeof window === 'undefined') {
    return null
  }

  return window.SpeechRecognition ?? window.webkitSpeechRecognition ?? null
}

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

/** 函数作用：停止当前语音识别；输入参数：无；输出参数：无返回值。 */
function stopSpeechRecognition() {
  if (!speechRecognition) {
    isListening.value = false
    interimSpeechText.value = ''
    return
  }

  speechRecognition.onresult = null
  speechRecognition.onerror = null
  speechRecognition.onend = null
  speechRecognition.stop()
  speechRecognition = null
  isListening.value = false
  interimSpeechText.value = ''
}

/** 函数作用：根据错误类型展示语音识别提示；输入参数：error 错误类型；输出参数：无返回值。 */
function setSpeechError(error: string) {
  if (error === 'not-allowed' || error === 'service-not-allowed') {
    speechError.value = '需要允许麦克风权限'
    return
  }

  if (error === 'no-speech') {
    speechError.value = '没有识别到语音'
    return
  }

  speechError.value = '语音输入暂时不可用'
}

/** 函数作用：把语音识别结果写入输入框；输入参数：event 语音识别结果事件；输出参数：无返回值。 */
function handleSpeechResult(event: SpeechRecognitionEvent) {
  let finalText = ''
  let interimText = ''

  for (let index = event.resultIndex; index < event.results.length; index += 1) {
    const result = event.results[index]
    const transcript = result?.[0]?.transcript ?? ''

    if (result?.isFinal) {
      finalText += transcript
    } else {
      interimText += transcript
    }
  }

  const normalizedFinalText = finalText.trim()
  if (normalizedFinalText) {
    const separator = content.value.trim() ? ' ' : ''
    content.value = `${content.value.trimEnd()}${separator}${normalizedFinalText}`
  }

  interimSpeechText.value = interimText.trim()
}

/** 函数作用：启动或停止浏览器原生语音识别；输入参数：无；输出参数：无返回值。 */
function toggleSpeechRecognition() {
  if (isListening.value) {
    stopSpeechRecognition()
    return
  }

  const SpeechRecognitionConstructor = getSpeechRecognitionConstructor()
  if (!SpeechRecognitionConstructor) {
    speechError.value = '当前浏览器不支持语音输入'
    return
  }

  speechError.value = ''
  interimSpeechText.value = ''
  speechRecognition = new SpeechRecognitionConstructor()
  speechRecognition.lang = 'zh-CN'
  speechRecognition.continuous = false
  speechRecognition.interimResults = true
  speechRecognition.onresult = handleSpeechResult
  speechRecognition.onerror = (event) => {
    setSpeechError(event.error)
    stopSpeechRecognition()
  }
  speechRecognition.onend = () => {
    speechRecognition = null
    isListening.value = false
    interimSpeechText.value = ''
  }

  try {
    speechRecognition.start()
    isListening.value = true
  } catch {
    speechError.value = '语音输入启动失败'
    stopSpeechRecognition()
  }
}

/** 函数作用：提交当前输入内容；输入参数：无；输出参数：无返回值。 */
function handleSubmit() {
  const nextContent = content.value.trim()

  if ((!nextContent && images.value.length === 0) || props.isStreaming) {
    return
  }

  emit('send', nextContent, enableWebSearch.value, [...images.value])
  stopSpeechRecognition()
  content.value = ''
  images.value = []
  imageError.value = ''
  speechError.value = ''
}

/** 函数作用：处理 Enter 发送、Shift+Enter 换行；输入参数：event 键盘事件；输出参数：无返回值。 */
function handleKeydown(event: KeyboardEvent) {
  if (event.key !== 'Enter' || event.shiftKey) {
    return
  }

  event.preventDefault()
  handleSubmit()
}

watch(
  () => props.isStreaming,
  (isStreaming) => {
    if (isStreaming) {
      stopSpeechRecognition()
    }
  },
)
</script>

<template>
  <form class="rounded-lg border border-zinc-200 bg-white px-3 py-1.5 shadow-sm" @submit.prevent="handleSubmit">
    <div v-if="images.length" class="mb-3 flex flex-wrap gap-2">
      <div
        v-for="(image, index) in images"
        :key="`${image.name}-${index}`"
        class="relative size-20 overflow-hidden rounded-md border border-zinc-200 bg-zinc-50"
      >
        <img :src="image.dataUrl" :alt="image.name" class="size-full object-cover" />
        <button
          type="button"
          class="absolute right-1 top-1 inline-flex size-6 items-center justify-center rounded-md bg-white/90 text-zinc-700 shadow-sm transition hover:bg-white hover:text-zinc-950"
          :aria-label="`移除 ${image.name}`"
          @click="removeImage(index)"
        >
          <X class="size-4" />
        </button>
      </div>
    </div>
    <div v-if="imageError" class="mb-2 text-xs text-red-600">{{ imageError }}</div>
    <div v-if="speechStatusText" class="mb-2 text-xs" :class="speechStatusClass">
      {{ speechStatusText }}
    </div>
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
        placeholder="给 My GPT 发送消息"
        class="max-h-40 min-h-10 flex-1 resize-none rounded-md border-0 bg-transparent px-2 py-1.5 text-sm leading-6 outline-none placeholder:text-zinc-400"
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
          :label="isListening ? '停止语音输入' : '语音输入'"
          :disabled="!isSpeechSupported"
          :class="{
            'bg-emerald-100 text-emerald-700 hover:bg-emerald-200 hover:text-emerald-800': isListening,
            'opacity-40': !isSpeechSupported,
          }"
          @click="toggleSpeechRecognition"
        >
          <MicOff v-if="isListening" class="size-5" />
          <Mic v-else class="size-5" />
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
