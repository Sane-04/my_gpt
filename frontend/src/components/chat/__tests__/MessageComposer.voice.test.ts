// 模块说明：前端 Vue 组件测试模块，验证聊天输入区语音输入交互。
import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import MessageComposer from '@/components/chat/MessageComposer.vue'
import type { VoiceErrorEvent, VoiceResultEvent, VoiceStateEvent, VoiceVolumeEvent } from '@/native/voiceInput'

type VoiceListenerEvent = VoiceResultEvent | VoiceErrorEvent | VoiceVolumeEvent | VoiceStateEvent

const mocks = vi.hoisted(() => ({
  voiceListeners: {} as Record<string, ((event: VoiceListenerEvent) => void) | undefined>,
  requestPermissionsMock: vi.fn(),
  initializeMock: vi.fn(),
  startListeningMock: vi.fn(),
  stopListeningMock: vi.fn(),
  cancelListeningMock: vi.fn(),
  addListenerMock: vi.fn(),
}))

/** 函数作用：查找语音主按钮；输入参数：wrapper 组件包装器；输出参数：按钮包装器。 */
function findVoiceButton(wrapper: ReturnType<typeof mount>) {
  return wrapper.findAll('button').find((button) => {
    const text = button.text()
    return text.includes('点击开始说话') || text.includes('点击结束识别') || text.includes('正在识别')
  })
}

vi.mock('@/native/voiceInput', () => ({
  isVoiceInputAvailable: () => true,
  voiceInput: {
    requestPermissions: mocks.requestPermissionsMock,
    initialize: mocks.initializeMock,
    startListening: mocks.startListeningMock,
    stopListening: mocks.stopListeningMock,
    cancelListening: mocks.cancelListeningMock,
    addListener: mocks.addListenerMock,
  },
}))

describe('MessageComposer voice input', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    Object.keys(mocks.voiceListeners).forEach((key) => {
      delete mocks.voiceListeners[key]
    })
    mocks.requestPermissionsMock.mockResolvedValue({ microphone: 'granted' })
    mocks.initializeMock.mockResolvedValue({ initialized: true })
    mocks.startListeningMock.mockResolvedValue({ started: true })
    mocks.stopListeningMock.mockResolvedValue({ stopping: true })
    mocks.cancelListeningMock.mockResolvedValue({ cancelled: true })
    mocks.addListenerMock.mockImplementation(async (eventName: string, listener: (event: VoiceListenerEvent) => void) => {
      mocks.voiceListeners[eventName] = listener
      return { remove: vi.fn() }
    })
  })

  it('点击开始语音识别后把最终结果填入输入框且不自动发送', async () => {
    const wrapper = mount(MessageComposer, {
      props: {
        isStreaming: false,
      },
    })

    await wrapper.get('button[aria-label="语音输入"]').trigger('click')
    const voiceButton = findVoiceButton(wrapper)
    expect(voiceButton).toBeTruthy()
    await voiceButton!.trigger('click')
    await flushPromises()

    expect(mocks.startListeningMock).toHaveBeenCalledWith({
      language: 'zh_cn',
      domain: 'iat',
      accent: 'henanese',
      vadEos: 8000,
    })

    mocks.voiceListeners.finalResult?.({ text: '中午吃烩面', sid: 'sid-1' })
    await nextTick()
    await flushPromises()

    expect((wrapper.get('textarea').element as HTMLTextAreaElement).value).toBe('中午吃烩面')
    expect(wrapper.emitted('send')).toBeUndefined()
  })

  it('再次点击语音按钮会结束录音并等待识别', async () => {
    const wrapper = mount(MessageComposer, {
      props: {
        isStreaming: false,
      },
    })

    await wrapper.get('button[aria-label="语音输入"]').trigger('click')
    const voiceButton = findVoiceButton(wrapper)
    expect(voiceButton).toBeTruthy()
    await voiceButton!.trigger('click')
    await flushPromises()

    const recordingButton = findVoiceButton(wrapper)
    expect(recordingButton).toBeTruthy()
    await recordingButton!.trigger('click')
    await flushPromises()

    expect(mocks.stopListeningMock).toHaveBeenCalled()
    expect(findVoiceButton(wrapper)?.text()).toContain('正在识别')
    expect(mocks.cancelListeningMock).not.toHaveBeenCalled()
  })

  it('点击取消语音会取消当前识别并保留语音模式', async () => {
    const wrapper = mount(MessageComposer, {
      props: {
        isStreaming: false,
      },
    })

    await wrapper.get('button[aria-label="语音输入"]').trigger('click')
    const voiceButton = findVoiceButton(wrapper)
    expect(voiceButton).toBeTruthy()
    await voiceButton!.trigger('click')
    await flushPromises()

    await wrapper.get('button[aria-label="取消语音"]').trigger('click')
    await flushPromises()

    expect(mocks.cancelListeningMock).toHaveBeenCalled()
    expect(findVoiceButton(wrapper)?.text()).toContain('点击开始说话')
    expect(wrapper.find('textarea').exists()).toBe(false)
  })

  it('文本超过两行后输入框自动增高且不超过上限', async () => {
    const wrapper = mount(MessageComposer, {
      props: {
        isStreaming: false,
      },
    })

    const textareaWrapper = wrapper.get('textarea')
    const textarea = textareaWrapper.element as HTMLTextAreaElement
    Object.defineProperty(textarea, 'scrollHeight', {
      configurable: true,
      value: 220,
    })

    await textareaWrapper.setValue('第一行\n第二行\n第三行\n第四行\n第五行')

    expect(textarea.style.height).toBe('160px')
    expect(textarea.style.overflowY).toBe('auto')
  })
})
