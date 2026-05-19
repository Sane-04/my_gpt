// 模块说明：前端工具模块，提供跨页面复用的纯函数能力。
import hljs from 'highlight.js/lib/common'
import katex from 'katex'
import MarkdownIt from 'markdown-it'

interface MathPlaceholder {
  token: string
  html: string
  displayMode: boolean
}

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
      return `<div class="code-block"><button class="code-copy-button" type="button">复制</button><pre><code class="hljs">${escapeHtml(code)}</code></pre></div>`
    }

    try {
      const highlighted = hljs.highlight(code, {
        language,
        ignoreIllegals: true,
      }).value

      return `<div class="code-block"><button class="code-copy-button" type="button">复制</button><pre><code class="hljs language-${language}">${highlighted}</code></pre></div>`
    } catch {
      return `<div class="code-block"><button class="code-copy-button" type="button">复制</button><pre><code class="hljs">${escapeHtml(code)}</code></pre></div>`
    }
  },
})

/**
 * 函数作用：把模型偶尔输出的独立方括号公式块归一化为标准块级公式。
 * 输入参数：content - 助手消息原文。
 * 输出参数：替换后的 Markdown 文本。
 */
function normalizeBracketMathBlocks(content: string) {
  return content.replace(/(^|\n)\[\s*\n([\s\S]*?)\n\s*\](?=\n|$)/g, (match, prefix: string, mathText: string) => {
    const compactMathText = mathText.trim()
    const looksLikeFormula = /[=\\_^{}]|[a-zA-Z]\s*[_=]|\b(sum|frac|sqrt|times|cdot)\b/.test(compactMathText)

    if (!looksLikeFormula) {
      return match
    }

    return `${prefix}$$\n${compactMathText}\n$$`
  })
}

/**
 * 函数作用：把 LaTeX 公式替换为占位符并保存 KaTeX HTML。
 * 输入参数：content - 助手消息原文。
 * 输出参数：包含占位符文本和公式 HTML 列表。
 */
function extractMathPlaceholders(content: string) {
  const placeholders: MathPlaceholder[] = []

  function _helper_renderMath(mathText: string, displayMode: boolean) {
    const token = `@@MATH_${placeholders.length}@@`

    try {
      const html = katex.renderToString(mathText.trim(), {
        displayMode,
        throwOnError: false,
        strict: false,
      })
      placeholders.push({
        token,
        html: displayMode ? `<div class="math-block">${html}</div>` : `<span class="math-inline">${html}</span>`,
        displayMode,
      })
    } catch {
      placeholders.push({
        token,
        html: displayMode
          ? `<div class="math-block math-fallback">${escapeHtml(mathText.trim())}</div>`
          : `<span class="math-inline math-fallback">${escapeHtml(mathText.trim())}</span>`,
        displayMode,
      })
    }

    return token
  }

  let nextContent = normalizeBracketMathBlocks(content)
  nextContent = nextContent.replace(/\$\$([\s\S]+?)\$\$|\\\[([\s\S]+?)\\\]/g, (_match, dollarMath: string, bracketMath: string) => {
    return _helper_renderMath(dollarMath ?? bracketMath ?? '', true)
  })
  nextContent = nextContent.replace(/\\\(([\s\S]+?)\\\)|(?<!\$)\$([^\n$]+?)\$(?!\$)/g, (_match, parenMath: string, dollarMath: string) => {
    return _helper_renderMath(parenMath ?? dollarMath ?? '', false)
  })

  return {
    content: nextContent,
    placeholders,
  }
}

/**
 * 函数作用：把 Markdown HTML 中的公式占位符替换为 KaTeX HTML。
 * 输入参数：html - Markdown 渲染结果；placeholders - 公式占位符列表。
 * 输出参数：替换公式后的 HTML。
 */
function restoreMathPlaceholders(html: string, placeholders: MathPlaceholder[]) {
  let nextHtml = html

  for (const placeholder of placeholders) {
    const paragraphPattern = new RegExp(`<p>\\s*${placeholder.token}\\s*</p>`, 'g')
    nextHtml = nextHtml.replace(paragraphPattern, placeholder.html)
    nextHtml = nextHtml.replaceAll(placeholder.token, placeholder.html)
  }

  return nextHtml
}

/**
 * 函数作用：把助手消息内容渲染为 Markdown HTML。
 * 输入参数：content - 助手消息原文。
 * 输出参数：返回可插入 v-html 的 HTML 字符串；异常时返回转义文本。
 */
export function renderMarkdown(content: string) {
  try {
    const { content: contentWithPlaceholders, placeholders } = extractMathPlaceholders(content)
    return restoreMathPlaceholders(markdown.render(contentWithPlaceholders), placeholders)
  } catch {
    return escapeHtml(content)
  }
}
