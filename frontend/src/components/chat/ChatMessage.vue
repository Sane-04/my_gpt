<!-- 模块说明：前端 Vue 组件模块，封装页面可复用的 UI 与交互片段。 -->
<script setup lang="ts">
import { CircleAlert, Download, User, Volume2, VolumeX } from 'lucide-vue-next'
import { computed, onBeforeUnmount, ref } from 'vue'
import IconButton from '@/components/base/IconButton.vue'
import ToolNotice from '@/components/chat/ToolNotice.vue'
import type { Message } from '@/types/domain'
import { escapeHtml, renderMarkdown } from '@/utils/markdown'

const props = defineProps<{
  message: Message
}>()

const isSpeaking = ref(false)
const speechSynthesisError = ref('')
const isSpeechSynthesisSupported = computed(() => (
  typeof window !== 'undefined'
  && 'speechSynthesis' in window
  && 'SpeechSynthesisUtterance' in window
))
const shouldShowSpeakButton = computed(() => (
  props.message.role === 'assistant'
  && props.message.content.trim().length > 0
))
const speechSynthesisStatusText = computed(() => {
  if (speechSynthesisError.value) {
    return speechSynthesisError.value
  }

  if (shouldShowSpeakButton.value && !isSpeechSynthesisSupported.value) {
    return '当前浏览器不支持朗读'
  }

  return ''
})

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

/** 函数作用：停止当前浏览器语音播报；输入参数：无；输出参数：无返回值。 */
function stopSpeaking() {
  if (!isSpeechSynthesisSupported.value) {
    return
  }

  window.speechSynthesis.cancel()
  isSpeaking.value = false
}

/** 函数作用：朗读或停止朗读助手消息；输入参数：无；输出参数：无返回值。 */
function toggleSpeaking() {
  if (!shouldShowSpeakButton.value) {
    return
  }

  if (!isSpeechSynthesisSupported.value) {
    speechSynthesisError.value = '当前浏览器不支持朗读'
    return
  }

  if (isSpeaking.value) {
    stopSpeaking()
    return
  }

  try {
    speechSynthesisError.value = ''
    window.speechSynthesis.cancel()
    const utterance = new window.SpeechSynthesisUtterance(props.message.content)
    utterance.lang = 'zh-CN'
    utterance.onend = () => {
      isSpeaking.value = false
    }
    utterance.onerror = () => {
      isSpeaking.value = false
      speechSynthesisError.value = '朗读失败，请检查浏览器语音播放权限'
    }
    isSpeaking.value = true
    window.speechSynthesis.speak(utterance)
  } catch {
    isSpeaking.value = false
    speechSynthesisError.value = '朗读启动失败，请换浏览器重试'
  }
}

/** 函数作用：下载消息中的图片；输入参数：dataUrl 图片 data URL、name 文件名；输出参数：无返回值。 */
function downloadImage(dataUrl: string, name: string) {
  const link = document.createElement('a')
  link.href = dataUrl
  link.download = name || 'generated-image.png'
  document.body.appendChild(link)
  link.click()
  link.remove()
}

onBeforeUnmount(() => {
  if (isSpeaking.value) {
    stopSpeaking()
  }
})
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

      <div v-if="shouldShowSpeakButton" class="mt-3 hidden justify-end sm:flex">
        <IconButton
          :label="isSpeechSynthesisSupported ? (isSpeaking ? '停止朗读' : '朗读回答') : '当前浏览器不支持朗读'"
          :disabled="!isSpeechSynthesisSupported"
          :class="{
            'bg-emerald-100 text-emerald-700 hover:bg-emerald-200 hover:text-emerald-800': isSpeaking,
            'opacity-40': !isSpeechSynthesisSupported,
          }"
          @click="toggleSpeaking"
        >
          <VolumeX v-if="isSpeaking" class="size-4" />
          <Volume2 v-else class="size-4" />
        </IconButton>
      </div>
      <div v-if="speechSynthesisStatusText" class="mt-2 text-right text-xs text-red-600">
        {{ speechSynthesisStatusText }}
      </div>

      <div v-if="message.images?.length" class="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
        <div
          v-for="(image, index) in message.images"
          :key="`${image.name}-${index}`"
          class="group relative overflow-hidden rounded-md border"
          :class="message.role === 'user' ? 'border-white/20' : 'border-zinc-200'"
        >
          <a :href="image.dataUrl" target="_blank" rel="noreferrer" class="block">
            <img :src="image.dataUrl" :alt="image.name" class="aspect-square w-full object-cover" />
          </a>
          <button
            v-if="image.source === 'generated'"
            type="button"
            class="absolute right-1.5 top-1.5 inline-flex size-8 items-center justify-center rounded-md bg-white/90 text-zinc-700 opacity-100 shadow-sm transition hover:bg-white hover:text-zinc-950 sm:opacity-0 sm:focus:opacity-100 sm:group-hover:opacity-100"
            :aria-label="`下载 ${image.name}`"
            @click="downloadImage(image.dataUrl, image.name)"
          >
            <Download class="size-4" />
          </button>
        </div>
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
</template>
