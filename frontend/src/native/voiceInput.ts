// 模块说明：前端原生能力模块，封装 Android 语音输入 Capacitor 插件。
import { Capacitor, registerPlugin } from '@capacitor/core'
import type { PluginListenerHandle } from '@capacitor/core'

export interface VoicePermissionStatus {
  microphone: 'prompt' | 'prompt-with-rationale' | 'granted' | 'denied'
}

export interface VoiceInputOptions {
  language?: string
  domain?: string
  accent?: string
  vadEos?: number
}

export interface VoiceInputStartResult {
  started: boolean
}

export interface VoiceInputStopResult {
  stopping: boolean
}

export interface VoiceInputCancelResult {
  cancelled: boolean
}

export interface VoiceInputInitializeResult {
  initialized: boolean
}

export interface VoiceResultEvent {
  text: string
  status?: number
  sid?: string
}

export interface VoiceErrorEvent {
  code: number
  message: string
  sid?: string
}

export interface VoiceVolumeEvent {
  level: number
}

export interface VoiceStateEvent {
  state: string
}

export interface VoiceInputPlugin {
  checkPermissions(): Promise<VoicePermissionStatus>
  requestPermissions(): Promise<VoicePermissionStatus>
  initialize(): Promise<VoiceInputInitializeResult>
  startListening(options?: VoiceInputOptions): Promise<VoiceInputStartResult>
  stopListening(): Promise<VoiceInputStopResult>
  cancelListening(): Promise<VoiceInputCancelResult>
  addListener(eventName: 'partialResult', listenerFunc: (event: VoiceResultEvent) => void): Promise<PluginListenerHandle>
  addListener(eventName: 'finalResult', listenerFunc: (event: VoiceResultEvent) => void): Promise<PluginListenerHandle>
  addListener(eventName: 'voiceError', listenerFunc: (event: VoiceErrorEvent) => void): Promise<PluginListenerHandle>
  addListener(eventName: 'volumeChanged', listenerFunc: (event: VoiceVolumeEvent) => void): Promise<PluginListenerHandle>
  addListener(eventName: 'stateChanged', listenerFunc: (event: VoiceStateEvent) => void): Promise<PluginListenerHandle>
}

export const voiceInput = registerPlugin<VoiceInputPlugin>('VoiceInput')

/** 函数作用：判断当前运行环境是否支持原生语音输入；输入参数：无；输出参数：是否支持。 */
export function isVoiceInputAvailable() {
  return Capacitor.getPlatform() === 'android'
}
