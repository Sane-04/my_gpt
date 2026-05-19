// 模块说明：ESLint 配置，统一前端 TypeScript 与 Vue 代码检查规则。
import js from '@eslint/js'
import vue from 'eslint-plugin-vue'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  {
    // 构建产物和依赖目录不参与检查，避免扫描第三方代码。
    ignores: ['dist', 'node_modules'],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  ...vue.configs['flat/recommended'],
  {
    languageOptions: {
      // 前端代码会直接使用浏览器全局对象，这里显式声明以避免 no-undef 误报。
      globals: {
        AbortController: 'readonly',
        AbortSignal: 'readonly',
        Headers: 'readonly',
        HTMLElement: 'readonly',
        HTMLInputElement: 'readonly',
        HTMLTextAreaElement: 'readonly',
        KeyboardEvent: 'readonly',
        ReadableStreamDefaultController: 'readonly',
        ReadableStream: 'readonly',
        RequestInit: 'readonly',
        Response: 'readonly',
        TextDecoder: 'readonly',
        TextEncoder: 'readonly',
        fetch: 'readonly',
        btoa: 'readonly',
        localStorage: 'readonly',
        window: 'readonly',
      },
    },
  },
  {
    files: ['**/*.vue'],
    languageOptions: {
      parserOptions: {
        // Vue 单文件组件中的 TS 片段交给 typescript-eslint 解析。
        parser: tseslint.parser,
      },
    },
    rules: {
      // 当前项目偏向紧凑模板和受控 Markdown 渲染，因此关闭这些展示类规则。
      'vue/html-self-closing': 'off',
      'vue/max-attributes-per-line': 'off',
      'vue/no-v-html': 'off',
      'vue/singleline-html-element-content-newline': 'off',
    },
  },
)
