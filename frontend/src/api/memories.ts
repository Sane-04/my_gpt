// 模块说明：前端 API 模块，统一封装后端请求、错误归一化和流式响应。
import { apiFetch } from '@/api/http'
import type {
  CreateMemoryRequest,
  DeleteMemoryResponse,
  MemoryDetailResponse,
  MemoryListResponse,
  UpdateMemoryRequest,
} from '@/types/api'

// 长期记忆 API：封装当前用户记忆列表、新增、更新和删除。
export const memoriesApi = {
  list() {
    return apiFetch<MemoryListResponse>('/api/memories')
  },
  create(request: CreateMemoryRequest) {
    return apiFetch<MemoryDetailResponse>('/api/memories', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  },
  update(memoryId: string, request: UpdateMemoryRequest) {
    return apiFetch<MemoryDetailResponse>(`/api/memories/${memoryId}`, {
      method: 'PUT',
      body: JSON.stringify(request),
    })
  },
  delete(memoryId: string) {
    return apiFetch<DeleteMemoryResponse>(`/api/memories/${memoryId}`, {
      method: 'DELETE',
    })
  },
}
