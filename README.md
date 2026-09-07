# 工业设备智能运维助手

这是一个面向求职展示的完整 AI 应用项目，将检索增强生成（RAG）、工具型 Agent、后端工程、离线评测和部署结合在工业设备维护场景中。

## 要解决的问题

维护工程师需要同时查阅设备手册、历史故障记录和传感器数据。普通聊天机器人可能给出缺少证据的建议，因此本项目强调来源引用、工具执行记录和人工确认。

目标用户是负责联网工业设备的维护工程师。系统提供检索和检查建议，但不会直接控制真实设备或替代安全关键决策。

## 当前已实现

- FastAPI 应用工厂和环境配置；
- PDF、Markdown 和纯文本解析，并保留来源与 PDF 页码；
- 具有稳定 ID、重叠窗口和引用元数据的文档切块；
- 文档上传、动态索引和可追溯搜索 API；
- 确定性哈希向量检索与 BM25 关键词检索；
- 基于 Reciprocal Rank Fusion（RRF）的排名融合；
- 基于查询词覆盖率的轻量候选重排；
- 可拒答的证据摘录生成器，以及经过检索候选校验的 `[S1]` 引用；
- 可显式启用的 OpenAI Responses 回答生成器，无引用或越界引用会被拒绝；
- 只读的历史故障查询和传感器区间分析工具；
- 最多执行三步、返回完整工具轨迹的确定性策略 Agent；
- 中文演示工作台：上传、原文检索、引用问答和三工具综合分析；
- SQLite 文本块持久化，重启后重建混合索引，并提供文档列表；
- 模型正文与引用列表统一编号，模型故障和引用错误返回明确状态码；
- 可配置共享访问口令、进程内限流、请求编号和 JSON 请求日志；
- 非 root Docker 镜像、持久卷，以及 GitHub CI 容器与浏览器测试；
- 可复现的 Recall@K、MRR 和平均延迟离线评测；
- Pytest 自动化测试和 Ruff 代码质量检查。

当前已经完成可本地演示的 RAG/Agent 应用。Milestone 2 的评测集扩充和真实质量提升、Milestone 5 的公开部署和最终求职材料仍未完成。CI 结果以仓库 Actions 中对应代码提交的实际运行记录为准。

2026-09-07 验收：代码提交 `43d9857` 的 **191 项 Python 测试、3 项浏览器测试、Ruff、Docker 构建及重启持久化检查全部通过**，见[本次 CI 记录](https://github.com/leonzhanglikang-png/industrial-maintenance-copilot/actions/runs/34089041071)。

默认演示使用确定性哈希向量和证据摘录式回答生成器，目的是在不依赖外部模型的情况下验证完整 RAG/Agent 链路。设置 `ANSWER_GENERATOR=openai` 后可改用 Responses API，但没有密钥也能运行全部离线功能。哈希向量不能被等同于语义 Embedding；现有 6 条小型评测集上四种检索方案的 Recall/MRR 暂时相同，因此尚不能声称混合检索带来了质量提升。

## 计划实现

1. 扩充检索评测集并接入真实语义 Embedding；
2. 完成真实模型在线验收、Agent 失败恢复和工具结果综合推理；
3. 完成公开 HTTPS 部署、负载与成本评测、求职材料；如需规模扩展，再迁移到 PostgreSQL/Qdrant。

## 本地运行

```bash
test -f .env || cp .env.example .env
UV_CACHE_DIR=.uv-cache uv sync --frozen
UV_CACHE_DIR=.uv-cache uv run python -m pytest
UV_CACHE_DIR=.uv-cache uv run uvicorn backend.app.main:app --reload --no-access-log
```

启动后访问：

- 中文工作台：`http://127.0.0.1:8000/`
- 健康检查：`http://127.0.0.1:8000/api/v1/health`
- 项目信息：`http://127.0.0.1:8000/api/v1/info`
- 文档上传：`POST http://127.0.0.1:8000/api/v1/documents/upload`
- 文档列表：`GET http://127.0.0.1:8000/api/v1/documents`
- 混合检索：`POST http://127.0.0.1:8000/api/v1/search`
- 引用回答：`POST http://127.0.0.1:8000/api/v1/answers`
- Agent 工作流：`POST http://127.0.0.1:8000/api/v1/agent/runs`
- API 文档：`http://127.0.0.1:8000/docs`

如需显式启用模型回答，在本机 `.env` 中配置，不要提交真实密钥：

```dotenv
ANSWER_GENERATOR=openai
LLM_API_KEY=your-local-key
LLM_MODEL=your-enabled-model
```

模型 API Key 只放在服务端 `.env`，不要填入页面。页面的“访问口令”对应另一个配置 `API_ACCESS_TOKEN`；它只在当前页面内存中保存。默认摘录模式不调用付费模型。引用错误返回 502，模型服务错误返回 503，均包含可定位日志的请求编号。

## 数据与访问控制

默认将解析后的文本块和元数据写入 `data/processed/documents.sqlite3`，该文件被 Git 忽略；原始上传文件解析后清理。`CHUNK_STORE_PATH` 可指定其他文件路径。重新启动服务后，系统从 SQLite 重建向量与 BM25 索引；重复上传按 Chunk ID 去重。

这仍是适合小型演示语料的全量内存检索：SQLite 保存文本块，向量与 BM25 统计在内存重建。新增数据会触发重建，不代表已经具备大规模向量数据库的性能。

设置 `API_ACCESS_TOKEN` 后，除健康检查外的业务 API 要求 `Authorization: Bearer <访问口令>`。生产模式 `APP_ENV=production` 要求口令至少 24 字符。它是共享口令保护，不是多用户账号和权限系统；默认每个直连客户端每分钟最多 60 个业务请求，可由 `RATE_LIMIT_PER_MINUTE` 调整。限流在单进程内计数，经过反向代理时需要另外设计可信客户端识别或网关限流。

请求日志输出到标准错误流，包含请求编号、方法、路由模板、状态码和耗时，不记录查询正文、文档内容或认证头。建议保留启动命令中的 `--no-access-log`，避免额外的原始 URL 访问日志。

## Docker 运行与 CI

有 Docker 的电脑可先在 `.env` 配置一个随机、至少 24 字符的 `API_ACCESS_TOKEN`，然后运行：

```bash
docker compose up --build -d
docker compose logs -f
```

打开 `http://127.0.0.1:8000/`，输入同一个访问口令。Compose 默认只监听本机端口，使用命名卷保留 SQLite 数据。`docker compose down` 保留卷；不要在需要保留知识库时使用 `down -v`。生产外网部署还需要具体主机、HTTPS 和持久磁盘配置，仓库中的 Docker 文件不等于已经公开上线。

[GitHub Actions](https://github.com/leonzhanglikang-png/industrial-maintenance-copilot/actions) 会在代码推送后运行 Python 测试、Ruff、JS 语法检查、Docker 构建、容器鉴权与重启持久化检查，再通过 Chromium 测试桌面三工具流程、上传后的检索、文本安全展示和手机布局。截图保存在对应运行的 `workbench-browser-check` artifact 中。纯 README/docs 更新不会重复运行代码 CI。

浏览器测试用依赖放在 `frontend/package.json`，只有测试需要 Node/npm；工作台运行本身只有 HTML、CSS、JS 和现有 Python 服务，不需要前端构建步骤。

运行四组检索基线评测：

```bash
UV_CACHE_DIR=.uv-cache uv run python -m backend.app.cli.evaluate_retrieval
```

## 目录结构

```text
backend/        FastAPI 应用和后续领域服务
frontend/       中文工作台静态页面和浏览器测试
data/           示例数据和被 Git 忽略的运行数据
docs/           系统架构与项目路线图
tests/          自动化测试
```

进一步阅读：

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)：中文功能总览、逐文件职责、请求调用链、测试说明；今天先读其中的 Day 15 阅读指导；
- [`docs/ROADMAP.md`](docs/ROADMAP.md)：功能里程碑和完成标准。

## 项目原则

每个功能都必须能够演示、能够自动化验证，并对应真实测量结果。模型生成内容必须区分文档证据与模型推断，涉及设备安全的操作始终由人类确认。
