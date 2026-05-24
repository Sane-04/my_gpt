<!-- 模块说明：前端页面模块，提供独立 Grok 搜索功能。 -->
<script setup lang="ts">
import { ExternalLink, LoaderCircle, Search } from 'lucide-vue-next'
import { storeToRefs } from 'pinia'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseTextarea from '@/components/base/BaseTextarea.vue'
import EmptyState from '@/components/base/EmptyState.vue'
import ErrorState from '@/components/base/ErrorState.vue'
import { useGrokSearchStore } from '@/stores/grokSearch'
import { renderMarkdown } from '@/utils/markdown'

const grokSearchStore = useGrokSearchStore()
const { answer, errorMessage, isLoading, mode, model, query, sources } = storeToRefs(grokSearchStore)

/** 函数作用：提交 Grok 搜索表单；输入参数：无；输出参数：Promise<void>。 */
async function handleSubmit() {
  await grokSearchStore.search()
}
</script>

<template>
  <main class="min-h-[calc(100vh-3.5rem)] px-4 py-6 sm:px-6">
    <section class="mx-auto w-full max-w-5xl">
      <div class="mb-6">
        <h1 class="text-lg font-semibold">Grok 搜索</h1>
        <p class="mt-1 text-sm text-zinc-500">使用独立 Grok 配置进行网页或 X 搜索。</p>
      </div>

      <form class="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm" @submit.prevent="handleSubmit">
        <BaseTextarea
          v-model="query"
          label="搜索内容"
          placeholder="输入要搜索的问题"
          :rows="3"
          :disabled="isLoading"
          required
        />

        <div class="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div class="inline-grid grid-cols-3 rounded-md bg-zinc-100 p-1">
            <button
              type="button"
              class="h-9 rounded-md px-4 text-sm font-medium transition"
              :class="mode === 'web' ? 'bg-white text-zinc-950 shadow-sm' : 'text-zinc-500'"
              :disabled="isLoading"
              @click="mode = 'web'"
            >
              网页
            </button>
            <button
              type="button"
              class="h-9 rounded-md px-4 text-sm font-medium transition"
              :class="mode === 'x' ? 'bg-white text-zinc-950 shadow-sm' : 'text-zinc-500'"
              :disabled="isLoading"
              @click="mode = 'x'"
            >
              X
            </button>
            <button
              type="button"
              class="h-9 rounded-md px-4 text-sm font-medium transition"
              :class="mode === 'auto' ? 'bg-white text-zinc-950 shadow-sm' : 'text-zinc-500'"
              :disabled="isLoading"
              @click="mode = 'auto'"
            >
              自动
            </button>
          </div>

          <BaseButton variant="primary" type="submit" :disabled="isLoading">
            <LoaderCircle v-if="isLoading" class="size-4 animate-spin" />
            <Search v-else class="size-4" />
            {{ isLoading ? '搜索中' : '搜索' }}
          </BaseButton>
        </div>
      </form>

      <ErrorState v-if="errorMessage" class="mt-4" title="搜索失败" :message="errorMessage" />

      <section v-if="answer" class="mt-5 rounded-lg border border-zinc-200 bg-white p-5 shadow-sm">
        <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 class="text-base font-semibold">搜索结果</h2>
          <span v-if="model" class="rounded-md bg-zinc-100 px-2 py-1 text-xs text-zinc-500">{{ model }}</span>
        </div>
        <div class="markdown-body" v-html="renderMarkdown(answer)" />
      </section>

      <section v-if="sources.length" class="mt-5">
        <h2 class="mb-3 text-base font-semibold">来源</h2>
        <div class="space-y-3">
          <article
            v-for="source in sources"
            :key="source.url || source.title || source.domain || 'source'"
            class="rounded-lg border border-zinc-200 bg-white p-4 shadow-sm"
          >
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <h3 class="truncate text-sm font-medium text-zinc-900">{{ source.title || source.domain || source.url }}</h3>
                <p v-if="source.snippet" class="mt-2 text-sm leading-6 text-zinc-500">{{ source.snippet }}</p>
                <div class="mt-2 truncate text-xs text-zinc-400">{{ source.domain || source.url }}</div>
              </div>
              <a
                v-if="source.url"
                :href="source.url"
                target="_blank"
                rel="noreferrer"
                class="inline-flex size-9 shrink-0 items-center justify-center rounded-md border border-zinc-200 text-zinc-500 transition hover:bg-zinc-100 hover:text-zinc-900"
                :aria-label="`打开 ${source.title || source.domain || '来源'}`"
              >
                <ExternalLink class="size-4" />
              </a>
            </div>
          </article>
        </div>
      </section>

      <section v-if="!answer && !isLoading" class="mt-5 rounded-lg border border-zinc-200 bg-white">
        <EmptyState title="开始 Grok 搜索" description="输入一个问题后，结果会在这里展示。">
          <template #icon>
            <Search class="size-6" />
          </template>
        </EmptyState>
      </section>
    </section>
  </main>
</template>
