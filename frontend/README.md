# My GPT Frontend

## 前端运行

| 命令 | 说明 |
| --- | --- |
| `npm install` | 安装前端依赖 |
| `npm run dev -- --host 127.0.0.1 --port 5173` | 启动本地开发服务器 |
| `npm run build` | 类型检查并构建生产包 |
| `npm test` | 运行 Vitest 单元测试 |
| `npm run lint` | 运行 ESLint |

## API 层结构

| 文件 | 职责 |
| --- | --- |
| `src/api/http.ts` | 底层 `fetch`、鉴权 header 和标准错误解析 |
| `src/api/session.ts` | 本地登录态读取、写入和清理 |
| `src/api/auth.ts` | 注册、登录、当前用户接口 |
| `src/api/conversations.ts` | 会话 CRUD 和会话消息分页读取 |
| `src/api/chat.ts` | 聊天流式接口 |
| `src/api/memories.ts` | 长期记忆 CRUD |
| `src/api/index.ts` | 统一导出真实后端 API |

## 消息加载与内存策略

| 策略 | 当前规则 |
| --- | --- |
| 首次进入会话 | 只加载最近 `20` 条消息 |
| 向上滚动 | 接近顶部时用 `before=最早消息 createdAt` 再加载更早 `20` 条 |
| 前端缓存 | Pinia 只保留最近使用的 `3` 个会话消息缓存 |
| LRU 淘汰 | 切到第 4 个会话时，释放最久未访问会话的消息和分页状态 |
| 删除会话 | 同步删除该会话的消息缓存 |

这样可以避免超长会话一次性进入 DOM 和 Pinia 内存，同时保留最近几个会话的快速切换体验。
