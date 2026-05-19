// 模块说明：前端工具模块，提供跨页面复用的纯函数能力。
import hljs from 'highlight.js/lib/common'
import MarkdownIt from 'markdown-it'

/**
 * 函数作用：转义 HTML 特殊字符，避免 Markdown 降级时注入页面。
 * 输入参数：content - 原始文本。
 * 输出参数：返回安全转义后的文本。
 */
export function escapeHtml(content: string) {
  return content
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

// Markdown 实例统一放在工具层，组件只负责展示渲染后的安全 HTML。
const markdown: MarkdownIt = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
  // 代码块优先使用 highlight.js，高亮失败时退回安全纯文本。
  highlight(code, language): string {
    const canHighlight = language && hljs.getLanguage(language)

    if (!canHighlight) {
      return `<div class="code-block"><button class="code-copy-button" type="button">复制</button><pre><code>${escapeHtml(code)}</code></pre></div>`
    }

    try {
      const highlighted = hljs.highlight(code, {
        language,
        ignoreIllegals: true,
      }).value

      return `<div class="code-block"><button class="code-copy-button" type="button">复制</button><pre><code class="hljs language-${language}">${highlighted}</code></pre></div>`
    } catch {
      return `<div class="code-block"><button class="code-copy-button" type="button">复制</button><pre><code>${escapeHtml(code)}</code></pre></div>`
    }
  },
})

/**
 * 函数作用：把助手消息内容渲染为 Markdown HTML。
 * 输入参数：content - 助手消息原文。
 * 输出参数：返回可插入 v-html 的 HTML 字符串；异常时返回转义文本。
 */
export function renderMarkdown(content: string) {
  try {
    return markdown.render(content)
  } catch {
    return escapeHtml(content)
  }
}
