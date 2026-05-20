# 后端联调接口清单

> 本文档由前端 TASK007 固化，后端实现应优先对齐这里的路径、方法和字段。

## 通用约定

| 项目 | 约定 |
| --- | --- |
| Base URL | `VITE_API_BASE_URL`，默认 `http://127.0.0.1:8000` |
| 鉴权 | `Authorization: Bearer <token>` |
| 错误响应 | `{ "error": { "code": "string", "message": "string" } }` |
| 流式协议 | fetch stream，每行一个 JSON 事件 |

## Auth

| 功能 | 方法 | 路径 | 请求 | 响应 |
| --- | --- | --- | --- | --- |
| 注册 | `POST` | `/api/auth/register` | `email`、`password`、`displayName` | `token`、`expires_at`、`user` |
| 登录 | `POST` | `/api/auth/login` | `email`、`password` | `token`、`expires_at`、`user` |
| 当前用户 | `GET` | `/api/auth/me` | 无 | `user` |

## Conversations

| 功能 | 方法 | 路径 | 请求 | 响应 |
| --- | --- | --- | --- | --- |
| 创建会话 | `POST` | `/api/conversations` | `title?` | `conversation` |
| 会话列表 | `GET` | `/api/conversations` | 无 | `conversations` |
| 会话详情 | `GET` | `/api/conversations/{id}` | 无 | `conversation` |
| 硬删除会话 | `DELETE` | `/api/conversations/{id}` | 无 | `deleted_id` |
| 会话消息 | `GET` | `/api/conversations/{id}/messages` | `limit?`、`before?` | `messages`、`hasMore` |

### Conversation Messages Pagination

| 参数 / 字段 | 方向 | 说明 |
| --- | --- | --- |
| `limit` | 请求 query | 每页消息数，默认 `20`，后端允许 `1-100` |
| `before` | 请求 query | ISO datetime，只返回该时间之前的更早消息 |
| `messages` | 响应 | 按 `createdAt` 正序返回 |
| `hasMore` | 响应 | 是否还有更早消息可继续向上加载 |

前端默认只加载最近 `20` 条消息；用户滚动到消息列表顶部附近时，再用当前最早消息的 `createdAt` 作为 `before` 游标加载上一页。前端 Pinia 只保留最近使用的 `3` 个会话消息缓存，超出后按 LRU 释放最久未访问会话的消息和分页状态。

## Chat Stream

| 功能 | 方法 | 路径 | 请求 | 响应 |
| --- | --- | --- | --- | --- |
| 聊天流 | `POST` | `/api/chat/stream` | `conversationId`、`content`、`enableWebSearch?`、`images?` | fetch stream |

### Chat Images

| 字段 | 说明 |
| --- | --- |
| `images` | 可选图片数组，最多 5 张 |
| `images[].name` | 图片文件名 |
| `images[].mimeType` | `image/png`、`image/jpeg`、`image/webp` 或 `image/gif` |
| `images[].size` | 单张图片原始大小，最大 10MB |
| `images[].dataUrl` | Base64 data URL，例如 `data:image/png;base64,...` |

### Stream Events

| 事件 | 示例 |
| --- | --- |
| `delta` | `{ "type": "delta", "delta": "文本增量" }` |
| `intent_started` | `{ "type": "intent_started" }` |
| `intent_finished` | `{ "type": "intent_finished", "intent": "image_generate", "confidence": "high", "message": "用户要求画图" }` |
| `tool_call_started` | `{ "type": "tool_call_started", "toolName": "web_search" }` |
| `tool_call_finished` | `{ "type": "tool_call_finished", "toolName": "web_search" }` |
| `image` | `{ "type": "image", "message": "已生成图片。", "image": { "name": "generated.png", "mimeType": "image/png", "size": 123, "dataUrl": "data:image/png;base64,...", "source": "generated" } }` |
| `sources` | `{ "type": "sources", "sources": [{ "id": "src_1", "title": "AP News", "url": "https://example.com", "domain": "example.com" }], "citationGroups": [{ "id": "cite_1", "label": "AP News", "sourceIds": ["src_1"] }] }` |
| `done` | `{ "type": "done" }` |
| `error` | `{ "type": "error", "message": "错误信息" }` |

联网搜索回答中的引用使用内部标记 `[[cite:src_1]]` 或 `[[cite:src_1,src_2]]`，前端会把它渲染为来源胶囊；不要把该标记作为普通文本展示给用户。

## Memories

| 功能 | 方法 | 路径 | 请求 | 响应 |
| --- | --- | --- | --- | --- |
| 记忆列表 | `GET` | `/api/memories` | 无 | `memories` |
| 新增记忆 | `POST` | `/api/memories` | `title`、`memory_key`、`content`、`source?` | `memory` |
| 更新记忆 | `PUT` | `/api/memories/{id}` | `title`、`memory_key`、`content`、`source?` | `memory` |
| 删除记忆 | `DELETE` | `/api/memories/{id}` | 无 | `deleted_id` |

## 字段命名

| 前端模型 | API 字段 |
| --- | --- |
| `memoryKey` | `memory_key` |
| `createdAt` | `created_at` 或响应进入前端后转换为 `createdAt` |
| `updatedAt` | `updated_at` 或响应进入前端后转换为 `updatedAt` |
