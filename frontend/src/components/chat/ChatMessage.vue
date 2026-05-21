<!-- 模块说明：前端 Vue 组件模块，封装页面可复用的 UI 与交互片段。 -->
<script setup lang="ts">
import { Capacitor, registerPlugin } from '@capacitor/core'
import { CircleAlert, Download, User, X } from 'lucide-vue-next'
import { computed, ref } from 'vue'
import ToolNotice from '@/components/chat/ToolNotice.vue'
import type { Message } from '@/types/domain'
import { escapeHtml, renderMarkdown } from '@/utils/markdown'

type MessageImage = NonNullable<Message['images']>[number]

interface ImageSaverPlugin {
  saveImageToGallery(options: {
    fileName: string
    mimeType: string
    base64Data: string
  }): Promise<{ uri: string }>
}

const ImageSaver = registerPlugin<ImageSaverPlugin>('ImageSaver')

const props = defineProps<{
  message: Message
}>()

const previewImage = ref<MessageImage | null>(null)
const imageSaveStatus = ref('')
let imageSaveStatusTimer: number | null = null

// 只有助手消息需要 Markdown 渲染；用户消息保持纯文本，避免不必要的 HTML 注入面。
const renderedContent = computed(() => {
  if (props.message.role !== 'assistant') {
    return ''
  }

  const renderedHtml = renderMarkdown(props.message.content)
  const sources = props.message.sources ?? []
  if (sources.length === 0) {
    return renderedHtml
  }

  const sourcesById = new Map(sources.map((source) => [source.id, source]))
  const citationGroupsByKey = new Map(
    (props.message.citationGroups ?? []).map((group) => [group.sourceIds.join(','), group]),
  )

  return renderedHtml.replace(/\[\[cite:([a-zA-Z0-9_,\-\s]+)\]\]/g, (_match, sourceIdsText: string) => {
    const sourceIds = sourceIdsText
      .split(',')
      .map((sourceId) => sourceId.trim())
      .filter((sourceId) => sourcesById.has(sourceId))
    if (sourceIds.length === 0) {
      return ''
    }

    const linkedSources = sourceIds.map((sourceId) => sourcesById.get(sourceId)).filter((source) => source !== undefined)
    const firstSource = linkedSources[0]
    if (!firstSource) {
      return ''
    }

    const citationKey = sourceIds.join(',')
    const citationGroup = citationGroupsByKey.get(citationKey)
    const fallbackLabel = linkedSources.length > 1
      ? `${firstSource.title || firstSource.domain || '来源'} +${linkedSources.length - 1}`
      : firstSource.title || firstSource.domain || '来源'
    const label = citationGroup?.label || fallbackLabel
    const sourceItems = linkedSources
      .map((source) => {
        let domain = source.domain || source.url
        try {
          domain = source.domain || new URL(source.url).hostname.replace(/^www\./, '')
        } catch {
          domain = source.domain || source.url
        }
        return `
          <span class="citation-source">
            <span class="citation-source-title">${escapeHtml(source.title || domain)}</span>
            ${source.snippet ? `<span class="citation-source-snippet">${escapeHtml(source.snippet)}</span>` : ''}
            <a class="citation-source-link" href="${escapeHtml(source.url)}" target="_blank" rel="noreferrer">${escapeHtml(domain)}</a>
          </span>
        `
      })
      .join('')
    const href = firstSource.url ? `data-href="${escapeHtml(firstSource.url)}"` : ''

    return `
      <span class="citation-capsule" tabindex="0" ${href}>
        ${escapeHtml(label)}
        <span class="citation-popover">${sourceItems}</span>
      </span>
    `
  })
})

/** 函数作用：处理助手 Markdown 内的复制按钮和引用胶囊点击；输入参数：event 鼠标事件；输出参数：无返回值。 */
async function handleMarkdownClick(event: MouseEvent) {
  const target = event.target
  if (!(target instanceof HTMLElement)) {
    return
  }

  const copyButton = target.closest('.code-copy-button')
  if (copyButton instanceof HTMLButtonElement) {
    const codeBlock = copyButton.closest('.code-block')
    const code = codeBlock?.querySelector('code')?.textContent ?? ''
    if (!code) {
      return
    }

    const originalText = copyButton.textContent || '复制'
    try {
      await navigator.clipboard.writeText(code)
      copyButton.textContent = '已复制'
      copyButton.dataset.state = 'success'
    } catch {
      copyButton.textContent = '复制失败'
      copyButton.dataset.state = 'error'
    }

    window.setTimeout(() => {
      copyButton.textContent = originalText
      delete copyButton.dataset.state
    }, 1200)
    return
  }

  const linkTarget = target.closest('a')
  if (linkTarget) {
    return
  }

  const capsule = target.closest('.citation-capsule')
  if (!(capsule instanceof HTMLElement)) {
    return
  }

  const href = capsule.dataset.href
  if (!href) {
    return
  }

  window.open(href, '_blank', 'noreferrer')
}

/** 函数作用：展示图片保存状态并自动清理；输入参数：message 状态文案；输出参数：无返回值。 */
function showImageSaveStatus(message: string) {
  imageSaveStatus.value = message
  if (imageSaveStatusTimer !== null) {
    window.clearTimeout(imageSaveStatusTimer)
  }
  imageSaveStatusTimer = window.setTimeout(() => {
    imageSaveStatus.value = ''
    imageSaveStatusTimer = null
  }, 1800)
}

/** 函数作用：解析 data URL 图片信息；输入参数：dataUrl 图片 data URL、name 文件名；输出参数：图片保存参数或 null。 */
function parseImageDataUrl(dataUrl: string, name: string) {
  const match = dataUrl.match(/^data:(image\/[a-zA-Z0-9.+-]+);base64,(.+)$/)
  if (!match) {
    return null
  }

  const mimeType = match[1]
  const extension = mimeType.split('/')[1]?.replace('jpeg', 'jpg') || 'png'
  const safeName = (name || `generated-image.${extension}`)
    .replace(/[\\/:*?"<>|]+/g, '-')
    .replace(/\s+/g, '-')
  return {
    mimeType,
    base64Data: match[2],
    fileName: safeName.includes('.') ? safeName : `${safeName}.${extension}`,
  }
}

/** 函数作用：打开图片预览弹层；输入参数：image 消息图片；输出参数：无返回值。 */
function openImagePreview(image: MessageImage) {
  previewImage.value = image
}

/** 函数作用：关闭图片预览弹层；输入参数：无；输出参数：无返回值。 */
function closeImagePreview() {
  previewImage.value = null
}

/** 函数作用：使用浏览器能力下载图片；输入参数：dataUrl 图片 data URL、name 文件名；输出参数：无返回值。 */
function downloadImageInBrowser(dataUrl: string, name: string) {
  const link = document.createElement('a')
  link.href = dataUrl
  link.download = name || 'generated-image.png'
  document.body.appendChild(link)
  link.click()
  link.remove()
}

/** 函数作用：下载消息中的图片；输入参数：dataUrl 图片 data URL、name 文件名；输出参数：Promise<void>。 */
async function downloadImage(dataUrl: string, name: string) {
  if (!Capacitor.isNativePlatform()) {
    downloadImageInBrowser(dataUrl, name)
    return
  }

  const imageData = parseImageDataUrl(dataUrl, name)
  if (!imageData) {
    downloadImageInBrowser(dataUrl, name)
    return
  }

  try {
    await ImageSaver.saveImageToGallery(imageData)
    showImageSaveStatus('已保存到相册')
  } catch {
    showImageSaveStatus('保存失败，已尝试浏览器下载')
    downloadImageInBrowser(dataUrl, name)
  }
}
</script>

<template>
  <!-- 工具消息使用独立结构，便于后续展示工具名称、参数和状态。 -->
  <ToolNotice
    v-if="message.role === 'tool'"
    :tool-name="message.toolName"
    :content="message.content"
  />

  <!-- 普通消息按角色区分左右方向和气泡样式。 -->
  <article
    v-else
    class="flex gap-3"
    :class="message.role === 'user' ? 'justify-end' : 'justify-start'"
  >
    <div
      v-if="message.role !== 'user'"
      class="mt-1 size-8 shrink-0 overflow-hidden rounded-md bg-zinc-100 dark:bg-zinc-800"
    >
      <img src="/cow.jpg" alt="助手头像" class="size-full object-cover" />
    </div>

    <div
      class="min-w-0 max-w-[min(720px,100%)] rounded-lg px-4 py-3 text-sm leading-6"
      :class="{
        'bg-zinc-950 text-white dark:bg-zinc-100 dark:text-zinc-950': message.role === 'user',
        'border border-zinc-200 bg-white text-zinc-900 shadow-sm dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-100': message.role !== 'user',
      }"
    >
      <!-- renderedContent 来自 markdown-it，且 html=false；这里仅用于展示受控 Markdown。 -->
      <div v-if="message.role === 'assistant'" class="markdown-body" @click="handleMarkdownClick" v-html="renderedContent" />
      <div v-else class="whitespace-pre-wrap break-words">{{ message.content }}</div>

      <div v-if="message.images?.length" class="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
        <div
          v-for="(image, index) in message.images"
          :key="`${image.name}-${index}`"
          class="group relative overflow-hidden rounded-md border"
          :class="message.role === 'user' ? 'border-white/20' : 'border-zinc-200'"
        >
          <button type="button" class="block w-full" :aria-label="`预览 ${image.name}`" @click="openImagePreview(image)">
            <img :src="image.dataUrl" :alt="image.name" class="aspect-square w-full object-cover" />
          </button>
          <button
            v-if="image.source === 'generated'"
            type="button"
            class="absolute right-1.5 top-1.5 inline-flex size-8 items-center justify-center rounded-md bg-white/90 text-zinc-700 opacity-100 shadow-sm transition hover:bg-white hover:text-zinc-950 sm:opacity-0 sm:focus:opacity-100 sm:group-hover:opacity-100"
            :aria-label="`下载 ${image.name}`"
            @click.stop="downloadImage(image.dataUrl, image.name)"
          >
            <Download class="size-4" />
          </button>
        </div>
      </div>
      <div v-if="imageSaveStatus" class="mt-2 text-xs text-emerald-600">
        {{ imageSaveStatus }}
      </div>

      <div
        v-if="message.status === 'streaming' || message.status === 'error'"
        class="mt-3 flex items-center gap-2 text-xs"
        :class="message.status === 'error' ? 'text-red-600' : 'text-zinc-500'"
      >
        <CircleAlert v-if="message.status === 'error'" class="size-3.5" />
        <span>{{ message.status === 'error' ? '生成失败' : message.processingText || '正在生成' }}</span>
      </div>
    </div>

    <div
      v-if="message.role === 'user'"
      class="mt-1 flex size-8 shrink-0 items-center justify-center rounded-md bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300"
    >
      <User class="size-4" />
    </div>
  </article>

  <Teleport to="body">
    <div
      v-if="previewImage"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/90 p-4"
      role="dialog"
      aria-modal="true"
      @click="closeImagePreview"
    >
      <button
        type="button"
        class="absolute right-4 top-4 inline-flex size-10 items-center justify-center rounded-md bg-white/10 text-white transition hover:bg-white/20"
        aria-label="关闭图片预览"
        @click.stop="closeImagePreview"
      >
        <X class="size-5" />
      </button>
      <img
        :src="previewImage.dataUrl"
        :alt="previewImage.name"
        class="max-h-full max-w-full rounded-md object-contain"
        @click.stop
      />
      <button
        v-if="previewImage.source === 'generated'"
        type="button"
        class="absolute bottom-4 right-4 inline-flex size-10 items-center justify-center rounded-md bg-white text-zinc-800 shadow-sm transition hover:bg-zinc-100"
        :aria-label="`保存 ${previewImage.name}`"
        @click.stop="downloadImage(previewImage.dataUrl, previewImage.name)"
      >
        <Download class="size-5" />
      </button>
    </div>
  </Teleport>
</template>
