# My GPT Backend

后端使用 FastAPI，并且本项目明确使用已有 Anaconda 环境 `sane`。不要为 TASK008 新建 conda 环境，也不要添加 Docker 或 docker-compose。

## 环境

| 项目 | 说明 |
| --- | --- |
| Conda 环境 | `sane` |
| 启动方式 | `conda run -n sane ...` |
| Python | 以本机 `sane` 环境为准 |
| Docker | 本阶段不使用 |

## 安装依赖

```powershell
conda run -n sane python -m pip install -r backend/requirements.txt
```

## 启动服务

在仓库根目录执行：

```powershell
cd backend
conda run -n sane python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

健康检查：

```powershell
Invoke-WebRequest http://127.0.0.1:8000/health
```

正常返回：

```json
{
  "status": "ok",
  "service": "my-gpt-backend"
}
```

## 测试

在仓库根目录执行：

```powershell
conda run -n sane python -m pytest backend/tests
```

## 本地数据库准备

| 项目 | 要求 |
| --- | --- |
| PostgreSQL | 目标版本 PostgreSQL 16 |
| 数据库 | 建议创建 `my_gpt` |
| pgvector | 后续 TASK009 迁移会启用 `vector` 扩展 |
| pg_jieba | 后续 TASK009 迁移会启用 jieba 中文分词 |

示例准备步骤：

```sql
CREATE DATABASE my_gpt;
```

## 数据库迁移

在仓库根目录执行：

```powershell
cd backend
conda run -n sane python -m alembic upgrade head
```

生成新迁移时执行：

```powershell
cd backend
conda run -n sane python -m alembic revision --autogenerate -m "describe change"
```

## Auth 接口

前端真实 API Client 使用以下登录接口，错误响应统一为 `{ "error": { "code": "...", "message": "..." } }`。

| 功能 | 方法 | 路径 | 说明 |
| --- | --- | --- | --- |
| 注册 | `POST` | `/api/auth/register` | 请求 `email`、`password`、`displayName`，返回 `token`、`expires_at`、`user` |
| 登录 | `POST` | `/api/auth/login` | 请求 `email`、`password`，返回 `token`、`expires_at`、`user` |
| 当前用户 | `GET` | `/api/auth/me` | 需要 `Authorization: Bearer <token>`，返回 `user` |

`users.password_hash` 只保存 bcrypt 哈希，禁止保存明文密码。JWT 默认有效期由 `JWT_EXPIRE_DAYS` 控制。

后续迁移阶段会在数据库中执行类似扩展初始化：

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

`pg_jieba` 的安装方式依赖本地 PostgreSQL 16 安装来源。若开发机暂时无法安装 `pg_jieba`，可以临时降级进行非检索功能开发，但第一阶段最终验收必须恢复 jieba 中文分词能力。

## 配置文件

复制 `.env.example` 为 `.env` 后按本机环境调整：

```powershell
Copy-Item backend/.env.example backend/.env
```

关键变量包括：

| 变量 | 说明 |
| --- | --- |
| `DATABASE_URL` | PostgreSQL 连接串 |
| `JWT_SECRET` | JWT 签名密钥 |
| `JWT_EXPIRE_DAYS` | JWT 有效期，默认 7 天 |
| `OPENAI_API_KEY` | OpenAI 或兼容服务 API Key |
| `OPENAI_BASE_URL` | OpenAI 兼容服务 base URL |
| `CHAT_MODEL` | 聊天模型；历史变量 `RESPONSES_MODEL` 仍兼容 |
| `EMBEDDING_API_KEY` | Embedding 服务 API Key；不回退到 `OPENAI_API_KEY` |
| `EMBEDDING_BASE_URL` | Embedding 兼容服务 base URL；不回退到 `OPENAI_BASE_URL` |
| `EMBEDDING_MODEL` | Embedding 模型 |
| `WEB_SEARCH_PROVIDER` | 聊天联网搜索提供商，可选 `serpapi` 或 `grok` |
| `SERPAPI_API_KEY` | SerpApi API Key，用于联网搜索 |
| `SERPAPI_TIMEOUT_SECONDS` | SerpApi 请求超时，默认 15 秒 |
| `GROK_API_KEY` | Grok 搜索 API Key，独立于聊天模型配置 |
| `GROK_BASE_URL` | Grok 搜索 API 地址，默认 `https://api.x.ai/v1` |
| `GROK_SEARCH_MODEL` | Grok 搜索模型，默认 `grok-4.3` |
| `GROK_SEARCH_TIMEOUT_SECONDS` | Grok 搜索请求超时，默认 60 秒 |
| `GROK_SEARCH_MAX_RESULTS` | Grok 搜索来源数量上限，默认 5 |
| `MODEL_HTTP_TIMEOUT_SECONDS` | 非流式模型请求超时，默认 60 秒 |
| `MODEL_STREAM_TIMEOUT_SECONDS` | 流式模型无数据读取超时，默认 180 秒 |
| `CONTEXT_WINDOW_SIZE` | 最近上下文消息数，默认 5 |
| `LONG_TERM_MEMORY_MAX_CHARS` | 长期记忆全文上限，默认 20000 |
| `SAVE_PROMPT_SNAPSHOTS` | 是否保存 Prompt 快照 |
| `MEMORY_DIR` | 长期记忆 Markdown 副本目录 |

## 聊天上下文与当前会话检索

| 能力 | 说明 |
| --- | --- |
| 上下文窗口 | 每次聊天请求会携带当前会话最近 `CONTEXT_WINDOW_SIZE` 条历史消息，并把当前用户消息追加到最后 |
| 消息 embedding | 用户消息和助手消息保存后会同步尝试生成 embedding，失败时记录 `embedding_status=failed` 和 `embedding_error`，不阻塞聊天 |
| 当前会话 FTS | `messages.fts_vector` 由 pg_jieba 触发器维护，可用于当前会话窗口外历史关键词检索 |
| 当前会话向量检索 | `messages.embedding` 使用 pgvector cosine 距离做语义召回 |
| 混合检索 | `hybrid_search_session_memory` 使用 RRF 融合 FTS 与向量召回结果，按当前用户和当前会话隔离，排除上下文窗口内消息并去重 |
| 时序检索 | `list_messages_by_chronological_position` 按当前会话时间线读取最早、最近或指定偏移消息，用于第一句、最后一句等确定性问题 |

## 长期记忆与记忆工具

| 能力 | 说明 |
| --- | --- |
| 长期记忆 API | `GET/POST/PUT/DELETE /api/memories`，按当前登录用户隔离 |
| 数据源 | 数据库 `long_term_memories` 为主，`metadata` 保存 `title`、`memory_key`、`source` |
| Markdown 副本 | 每次 CRUD 后同步到 `MEMORY_DIR/{user_id}/long_term_memory.md`，数据库和文件冲突时以数据库为准重建 |
| 模型注入 | 每次聊天请求都会携带当前用户长期记忆全文，最多 `LONG_TERM_MEMORY_MAX_CHARS` 字符 |
| 记忆事件 | 创建、更新、删除长期记忆会写入 `memory_events` |
| 记忆工具 | 第一阶段提供 `search_session_memory`、`get_session_messages_by_position`、`list_long_term_memory`、`save_long_term_memory`、`update_long_term_memory` |
| 工具审计 | 每次工具调用会写入 `tool_call_events`，记录参数、结果、状态和错误 |

注意：如果模型回复“需要调用 save_long_term_memory”但没有实际保存，请先检查 `tool_call_events` 审计记录和模型服务的工具调用兼容性。部分第三方 OpenAI-compatible 服务可能只实现文本流，未完整兼容 `chat_completions` 或 `responses` 的工具调用字段。

## 聊天联网搜索 Provider

聊天工具 `web_search` 会按 `WEB_SEARCH_PROVIDER` 选择搜索来源。`serpapi` 使用现有 SerpApi Google Search；`grok` 使用 `GROK_API_KEY`、`GROK_BASE_URL` 和 `GROK_SEARCH_MODEL` 调用 Grok 搜索。前端仍使用聊天输入框里的“联网搜索”开关，不提供单独搜索页。

| Provider | 必需配置 | 说明 |
| --- | --- |
| `serpapi` | `SERPAPI_API_KEY` | 保留原有 SerpApi 搜索路径 |
| `grok` | `GROK_API_KEY`、`GROK_BASE_URL`、`GROK_SEARCH_MODEL` | 使用 Grok 搜索作为聊天联网搜索来源 |

## 目录结构

```text
backend/
  app/
    api/
    core/
    db/
    models/
    repositories/
    schemas/
    services/
    tools/
    prompts/
    main.py
  data/
    memories/
  tests/
```
