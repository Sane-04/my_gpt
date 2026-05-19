# My GPT

在线访问：<https://cyandsane.bond>

My GPT 是一个面向个人使用的 AI 聊天应用，提供接近 ChatGPT 的基础体验，并加入用户隔离、会话历史、长期记忆、当前会话检索、图片输入、联网搜索和流式响应能力。模型服务可通过环境变量自行配置，支持 OpenAI 官方接口或兼容接口，也可以独立配置对话模型与 Embedding 服务。项目采用前后端分离架构，支持本地开发，也支持使用 Docker Compose + Caddy 一键部署到服务器。

## 功能概览

| 功能 | 说明 |
| --- | --- |
| 用户鉴权 | 支持注册、登录、退出，使用 JWT 维护登录态 |
| 会话管理 | 支持新建、切换、删除会话，历史消息按用户隔离 |
| 流式聊天 | 后端通过 fetch stream 返回模型增量内容 |
| Markdown 回复 | 助手消息支持 Markdown、代码块、复制按钮和引用胶囊 |
| 图片输入 | 支持 png、jpeg、webp、gif 图片作为聊天输入 |
| 联网搜索 | 可通过 SerpApi 搜索网页，并在回答中显示来源引用 |
| 模型可配置 | 支持自定义模型名称、API Key、base_url 和独立 Embedding 服务 |
| 当前会话检索 | 支持搜索上下文窗口外的当前会话历史消息 |
| 长期记忆 | 支持新增、编辑、删除长期记忆，并同步 Markdown 副本 |
| 工具审计 | 工具调用记录会写入数据库，便于排查和审计 |
| Docker 部署 | 使用 Caddy 自动 HTTPS，PostgreSQL 使用 pgvector 镜像 |

## 项目亮点

| 亮点 | 说明 |
| --- | --- |
| 长期记忆双存储 | 数据库作为主数据源，Markdown 文件作为可读副本 |
| 混合检索基础 | 当前会话历史支持 FTS 与 embedding 召回融合 |
| 流式优先 | 聊天接口按流式输出设计，前端逐段展示回复 |
| 可部署性 | Docker Compose 编排 Caddy、后端、迁移任务、PostgreSQL 和前端构建 |
| 自动 HTTPS | Caddy 自动申请和续期 `cyandsane.bond` 的 TLS 证书 |
| 模型服务可替换 | 对话模型和 Embedding 服务都通过环境变量配置，便于切换官方或兼容服务 |
| 配置清晰 | 后端、前端分别使用 `.env.example` 管理配置示例 |

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 前端 | Vue 3、TypeScript、Vite、Pinia、Vue Router、Tailwind CSS、markdown-it |
| 后端 | FastAPI、SQLAlchemy 2、Alembic、Pydantic Settings、JWT |
| 数据库 | PostgreSQL 16、pgvector |
| 模型接口 | OpenAI Chat Completions 兼容接口、Embedding 兼容接口 |
| 部署 | Docker Compose、Caddy |

## 目录结构

```text
my_gpt/
  backend/              # FastAPI 后端
    app/
    alembic/
    tests/
    Dockerfile
    requirements.txt
    .env.example
  frontend/             # Vue 前端
    src/
    Dockerfile
    .env.example
  Caddyfile             # Caddy HTTPS 和反代配置
  docker-compose.yml    # 生产部署编排
  README.md
```

## 环境变量

| 文件 | 说明 |
| --- | --- |
| `backend/.env.example` | 后端、数据库、模型、CORS、记忆目录等配置示例 |
| `frontend/.env.example` | 前端运行模式和生产 API 地址配置示例 |
| `backend/.env` | 本地或服务器实际后端配置，包含密钥，不应提交 |
| `frontend/.env.local` | 前端本地开发配置，不应提交 |

生产部署时，`backend/.env` 至少需要正确配置：

对话模型和 Embedding 服务可以独立配置，按服务商调整 `OPENAI_BASE_URL`、`RESPONSES_MODEL`、`EMBEDDING_BASE_URL` 和 `EMBEDDING_MODEL` 即可。

| 配置 | 说明 |
| --- | --- |
| `POSTGRES_DB` | PostgreSQL 数据库名 |
| `POSTGRES_USER` | PostgreSQL 用户 |
| `POSTGRES_PASSWORD` | PostgreSQL 密码，生产必须使用强密码 |
| `DATABASE_URL` | Docker 部署时主机名使用 `postgres` |
| `JWT_SECRET` | JWT 签名密钥，生产必须使用强随机字符串 |
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` | 对话模型服务配置 |
| `EMBEDDING_API_KEY` / `EMBEDDING_BASE_URL` | Embedding 服务配置 |
| `SERPAPI_API_KEY` | 联网搜索配置 |

Docker 部署中的 `DATABASE_URL` 示例：

```env
DATABASE_URL=postgresql+asyncpg://postgres:your-password@postgres:5432/my_gpt
```

本地直接运行后端时，通常使用：

```env
DATABASE_URL=postgresql+asyncpg://postgres:your-password@127.0.0.1:5432/my_gpt
```

## 本地开发

后端：

```powershell
cd backend
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m alembic upgrade head
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

前端：

```powershell
cd frontend
npm install
Copy-Item .env.example .env.local
npm run dev -- --host 127.0.0.1 --port 5173
```

常用验证：

```powershell
cd backend
python -m pytest --collect-only -q

cd ../frontend
npm run build
```

## Docker 部署

服务器建议将项目放在：

```text
/usr/project/my_gpt
```

部署步骤：

```bash
cd /usr/project
git clone <你的仓库地址> my_gpt
cd /usr/project/my_gpt

cp backend/.env.example backend/.env
nano backend/.env

docker compose up -d --build
```

启动后，`migrate` 服务会自动执行：

```bash
alembic upgrade head
```

查看日志：

```bash
docker compose logs migrate
docker compose logs -f backend
docker compose logs -f caddy
```

访问：

```text
https://cyandsane.bond
https://cyandsane.bond/health
```

## 数据持久化

| Volume | 保存内容 |
| --- | --- |
| `postgres_data` | PostgreSQL 数据 |
| `memory_data` | 长期记忆 Markdown 文件 |
| `frontend_dist` | 前端构建产物 |
| `caddy_data` | Caddy 证书数据 |
| `caddy_config` | Caddy 运行配置数据 |

普通重启或重新构建不会删除这些数据。不要在生产环境随意执行：

```bash
docker compose down -v
```

该命令会删除 volume，导致数据库和持久化文件丢失。

## 常用命令

| 命令 | 说明 |
| --- | --- |
| `docker compose up -d --build` | 构建并启动全部服务 |
| `docker compose ps` | 查看服务状态 |
| `docker compose logs -f caddy` | 查看 HTTPS 和反代日志 |
| `docker compose logs -f backend` | 查看后端日志 |
| `docker compose logs migrate` | 查看数据库迁移日志 |
| `docker compose restart backend` | 重启后端 |
| `docker compose down` | 停止并删除容器，保留 volume |

## 部署注意事项

| 项目 | 说明 |
| --- | --- |
| DNS | `cyandsane.bond` 需要解析到服务器公网 IP |
| 端口 | 服务器安全组和防火墙需要开放 `80`、`443` |
| HTTPS | Caddy 会自动申请证书，首次启动时需要公网可访问 |
| 数据库 | 后端和迁移服务通过 Docker 网络访问 `postgres` 服务 |
| 前端 API | 生产构建默认使用同源 `/api`，由 Caddy 反代到后端 |
| 密钥 | 不要提交真实 `.env`，只提交 `.env.example` |
