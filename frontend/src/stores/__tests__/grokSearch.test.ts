// 模块说明：前端测试模块，验证独立 Grok 搜索 store 状态流转。
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { grokSearchApi } from '@/api'
import { useGrokSearchStore } from '@/stores/grokSearch'

describe('useGrokSearchStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('可以执行 Grok 搜索并保存回答和来源', async () => {
    vi.spyOn(grokSearchApi, 'search').mockResolvedValue({
      answer: 'Grok 搜索回答',
      sources: [
        {
          title: '来源标题',
          url: 'https://example.com',
          domain: 'example.com',
          snippet: '来源摘要',
        },
      ],
      model: 'grok-4.3',
    })
    const grokSearchStore = useGrokSearchStore()
    grokSearchStore.query = '今天有什么新闻'
    grokSearchStore.mode = 'web'

    await grokSearchStore.search()

    expect(grokSearchStore.answer).toBe('Grok 搜索回答')
    expect(grokSearchStore.sources[0]?.domain).toBe('example.com')
    expect(grokSearchStore.model).toBe('grok-4.3')
    expect(grokSearchStore.errorMessage).toBe('')
  })

  it('空输入时不发起请求并展示错误', async () => {
    const searchSpy = vi.spyOn(grokSearchApi, 'search')
    const grokSearchStore = useGrokSearchStore()
    grokSearchStore.query = '   '

    await grokSearchStore.search()

    expect(searchSpy).not.toHaveBeenCalled()
    expect(grokSearchStore.errorMessage).toBe('请输入搜索内容')
  })

  it('搜索失败时保存错误信息并结束加载态', async () => {
    vi.spyOn(grokSearchApi, 'search').mockRejectedValue(new Error('GROK_SEARCH_FAILED'))
    const grokSearchStore = useGrokSearchStore()
    grokSearchStore.query = '测试'

    await grokSearchStore.search()

    expect(grokSearchStore.errorMessage).toBe('GROK_SEARCH_FAILED')
    expect(grokSearchStore.isLoading).toBe(false)
  })
})
