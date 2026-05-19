<!-- 模块说明：前端页面模块，承接路由页面的状态组织和用户操作。 -->
<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import BaseButton from '@/components/base/BaseButton.vue'
import BaseInput from '@/components/base/BaseInput.vue'
import ErrorState from '@/components/base/ErrorState.vue'
import { useAuthStore } from '@/stores/auth'
import type { AuthMode } from '@/types/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const mode = ref<AuthMode>('login')
const email = ref('')
const password = ref('')
const displayName = ref('')

// 文案随登录/注册模式切换，避免模板里堆叠条件表达式。
const title = computed(() => (mode.value === 'login' ? '登录 My GPT' : '注册 My GPT'))
const submitText = computed(() => (mode.value === 'login' ? '登录' : '注册并登录'))
const switchText = computed(() => (mode.value === 'login' ? '还没有账号？注册' : '已有账号？登录'))

/** 函数作用：提交登录或注册表单；输入参数：无；输出参数：Promise<void>。 */
async function handleSubmit() {
  try {
    if (mode.value === 'login') {
      await authStore.login({
        email: email.value,
        password: password.value,
      })
    } else {
      await authStore.register({
        email: email.value,
        password: password.value,
        displayName: displayName.value,
      })
    }
  } catch {
    // 失败原因已经由 authStore.errorMessage 展示在表单上方，页面层只负责阻止异常冒泡。
    return
  }

  // 保护路由跳转到登录页时会带 redirect，登录成功后回到用户原本想访问的页面。
  const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/chat'
  await router.push(redirect)
}

/** 函数作用：切换登录/注册模式并清空旧错误；输入参数：无；输出参数：无返回值。 */
function toggleMode() {
  authStore.errorMessage = ''
  mode.value = mode.value === 'login' ? 'register' : 'login'
}
</script>

<template>
  <main class="flex min-h-screen items-center justify-center bg-zinc-50 px-4 py-8 text-zinc-950">
    <section class="w-full max-w-sm rounded-lg border border-zinc-200 bg-white p-6 shadow-sm">
      <div>
        <h1 class="text-xl font-semibold">{{ title }}</h1>
        <p class="mt-2 text-sm leading-6 text-zinc-500">登录态会按后端配置保存并自动恢复。</p>
      </div>

      <!-- 登录/注册模式切换，TASK003 暂不拆成复杂表单组件。 -->
      <div class="mt-5 grid grid-cols-2 rounded-md bg-zinc-100 p-1">
        <button
          type="button"
          class="h-9 rounded-md text-sm font-medium transition"
          :class="mode === 'login' ? 'bg-white text-zinc-950 shadow-sm' : 'text-zinc-500'"
          @click="mode = 'login'"
        >
          登录
        </button>
        <button
          type="button"
          class="h-9 rounded-md text-sm font-medium transition"
          :class="mode === 'register' ? 'bg-white text-zinc-950 shadow-sm' : 'text-zinc-500'"
          @click="mode = 'register'"
        >
          注册
        </button>
      </div>

      <!-- 后端鉴权错误统一展示在表单上方。 -->
      <ErrorState
        v-if="authStore.errorMessage"
        class="mt-5"
        title="鉴权失败"
        :message="authStore.errorMessage"
      />

      <!-- 注册模式额外收集昵称，登录态最终统一写入 authStore。 -->
      <form class="mt-6 space-y-4" @submit.prevent="handleSubmit">
        <BaseInput
          v-if="mode === 'register'"
          v-model="displayName"
          label="昵称"
          placeholder="你的名字"
          autocomplete="name"
          required
          :disabled="authStore.isLoading"
        />
        <BaseInput
          v-model="email"
          label="邮箱"
          placeholder="you@example.com"
          type="email"
          autocomplete="email"
          required
          :disabled="authStore.isLoading"
        />
        <BaseInput
          v-model="password"
          label="密码"
          placeholder="请输入密码"
          type="password"
          autocomplete="current-password"
          required
          :disabled="authStore.isLoading"
        />
        <BaseButton class="w-full" variant="primary" type="submit" :disabled="authStore.isLoading">
          {{ authStore.isLoading ? '处理中' : submitText }}
        </BaseButton>
      </form>

      <button
        type="button"
        class="mt-5 w-full text-center text-sm font-medium text-zinc-600 transition hover:text-zinc-950"
        @click="toggleMode"
      >
        {{ switchText }}
      </button>
    </section>
  </main>
</template>
