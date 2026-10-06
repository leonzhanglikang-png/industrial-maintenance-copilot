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
- 可配置的 OpenAI 兼容语义向量适配器，批量调用、响应校验和明确失败处理（真实服务待验收）；
- 基于 Reciprocal Rank Fusion（RRF）的排名融合；
- 基于查询词覆盖率的轻量候选重排；
- 可拒答的证据摘录生成器，以及经过检索候选校验的 `[S1]` 引用；
- 可显式启用的 OpenAI Responses 回答生成器，无引用或越界引用会被拒绝；
- Chat Completions 回答适配器，DeepSeek 已完成 3 次授权真调用冒烟验收，保留引用校验、输出上限和安全失败处理；
- 只读的历史故障查询和传感器区间分析工具；
- 最多执行三步、返回完整工具轨迹的确定性策略 Agent；
- Agent 工具异常时立即停止，保留已完成步骤与引用，并在工作台显示失败步骤；
- 中文演示工作台：上传、原文检索、引用问答和三工具综合分析；
- SQLite 文本块持久化，重启后重建混合索引，并提供文档列表；
- 模型正文与引用列表统一编号，模型故障和引用错误返回明确状态码；
- 可配置共享访问口令、进程内限流、请求编号和 JSON 请求日志；
- 非 root Docker 镜像、持久卷，以及 GitHub CI 容器与浏览器测试；
- 可复现的 Recall@K、MRR 和平均延迟离线评测；
- 独立的 60 题合成检索基准、来源与标注校验、逐题命中和漏检诊断（尚待人工审核）；
- Pytest 自动化测试和 Ruff 代码质量检查。

当前已经完成可本地演示的 RAG/Agent 应用。Milestone 2 已有 60 题合成评测草案，但人工审核、独立测试集和真实质量提升仍未完成；Milestone 5 的公开部署和最终求职材料也仍未完成。CI 结果以对应代码提交的实际运行记录为准。

2026-10-06 验收：代码提交 `f78dba1` 的 **294 项 Python 测试、5 项浏览器测试、Ruff、Docker 构建及重启持久化检查全部通过**，见[本次 CI 记录](https://github.com/leonzhanglikang-png/industrial-maintenance-copilot/actions/runs/37451668316)。CI 不调用付费模型；另在本机完成 3 次授权 DeepSeek 真调用。Embedding 仍只有模拟接口验证。

默认演示使用确定性哈希向量和证据摘录式回答生成器，目的是在不依赖外部模型的情况下验证完整 RAG/Agent 链路。设置 `ANSWER_GENERATOR=openai` 后可改用 Responses API，但没有密钥也能运行全部离线功能。哈希向量不能被等同于语义 Embedding；旧 6 题上四方案的 Recall/MRR 相同，新增 60 题未审核合成基准上 BM25 的 Recall@5 为 100%，当前混合重排为 96.67%，不能声称混合方案优于 BM25 或代表生产质量。

## 计划实现

1. 人工审核检索标注、建立独立测试集并完成语义 Embedding 的真实调用与对比验收；
2. 扩展回答质量评测、Agent 失败后的恢复策略和工具结果综合推理（DeepSeek 小样本真调用已验证）；
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

模型 API Key 只放在服务端 `.env`，不要填入页面。页面的“访问口令”对应另一个配置 `API_ACCESS_TOKEN`；它只在当前页面内存中保存。默认哈希检索＋摘录回答组合不调用付费模型。直接调用 `/answers` 时，引用错误返回 502，模型服务错误返回 503，均包含可定位日志的请求编号。

### DeepSeek 回答配置

在本机 `.env` 设置后重启服务（不要复制到 `.env.example` 或提交密钥）：

```dotenv
ANSWER_GENERATOR=chat_completions
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=your-local-deepseek-key
LLM_MODEL=deepseek-flash
LLM_TIMEOUT_SECONDS=30
CHAT_MAX_TOKENS=512
CHAT_DISABLE_THINKING=true
```

DeepSeek 使用 Chat Completions，而 `ANSWER_GENERATOR=openai` 保留原来的 Responses 协议；不是只换地址就能兼容。模型名与禁用思考参数依据 [DeepSeek 官方文档](https://api-docs.deepseek.com/)。其他兼容服务请使用自己的模型，并先关闭 DeepSeek 专用扩展 `CHAT_DISABLE_THINKING=false`，逐家验收参数支持。

Chat 适配器禁用自动重试。截断、过滤或意外工具调用不作为完整回答返回；引用越界返回 502，服务或不完整响应返回 503。保留离线模式 `ANSWER_GENERATOR=extractive`。聊天模型与 Embedding 服务独立，DeepSeek 聊天密钥不要直接当作向量服务配置。

2026-10-06：经授权实际调用 3 次，验证有引用回答、证据不足拒答、Agent 三工具流程，总计 1489 token。使用本地路由、隔离的合成手册及 BM25，未读取上传库。这是小样本连通性与行为验收，不是全面质量、公开部署或语义检索验收；详见架构说明顶部。

### 可选：启用语义向量

只编辑本机 `.env`，不要提交密钥。向量模型与回答模型独立配置；`ANSWER_GENERATOR=extractive` 不代表语义检索也免费或离线。

```dotenv
EMBEDDING_PROVIDER=openai
EMBEDDING_BASE_URL=https://api.openai.com/v1
EMBEDDING_API_KEY=your-local-embedding-key
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSION=1536
EMBEDDING_TIMEOUT_SECONDS=30
```

修改后重启服务。默认仍是 `EMBEDDING_PROVIDER=hash`，无需密钥。上述模型的默认输出为 1536 维，接口使用 `encoding_format="float"`，依据 [OpenAI 官方文档](https://developers.openai.com/api/docs/guides/embeddings)。`EMBEDDING_DIMENSION` 只校验模型输出，不请求降维；使用兼容服务时，需要按其模型填写地址、名称与原生维度，兼容性须实测。

启用后，文档块和查询会发送到配置的模型服务，可能产生费用。不要上传未经许可的资料。当前 SQLite 只保存文本，启动和语料变化时重新生成向量；大语料的缓存与增量优化尚未实现。模型错误不会自动回退哈希，API 返回安全的 503。Embedding 仍未配置真实服务，接入测试使用模拟 HTTP；DeepSeek 回答真调用不替代向量验收。

Agent 的 `/agent/runs` 有独立的执行结果约定：工具开始执行后失败，会返回 HTTP 200 的执行记录，`stopped_reason="tool_failure"`，最后一步为 `failed`；已完成的答案和引用保留，后续工具停止。HTTP 200 只表示拿到了记录，不表示分析成功。运行前的配置错误仍返回 503。当前不支持自动重试或断点续跑。

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

运行四组检索基线评测（旧 6 题演示集）：

```bash
UV_CACHE_DIR=.uv-cache uv run python -m backend.app.cli.evaluate_retrieval
```

运行新的独立基准（20 个候选文本块、60 道题）：

```bash
UV_CACHE_DIR=.uv-cache uv run python -m backend.app.cli.evaluate_retrieval --dataset data/evaluation/maintenance_benchmark.json
```

添加 `--details` 可查看逐题相关块、返回块、漏检块与指标。输出包含数据来源、`review_status` 和 SHA-256 指纹。该基准由 AI 编写，当前为 `unreviewed`，不是人工标注或真实设备数据；预切块评测不包含文档解析、答案生成或在线负载。评测不会修改 SQLite 或在线知识库，具体结果与审核指导见架构说明顶部。

配置好向量服务后，显式添加 `--include-semantic` 可增加语义向量、语义混合、语义混合重排三组对比：

```bash
UV_CACHE_DIR=.uv-cache uv run python -m backend.app.cli.evaluate_retrieval --dataset data/evaluation/maintenance_benchmark.json --include-semantic --details
```

这会向模型服务发送基准语料与问题，可能计费；不带此开关始终只测原来的四组离线方案，不受应用的向量模式影响。60 题基准的 80 条唯一文本只批量嵌入一次，并复用于不同 K 和算法。报告单列 `embedding_elapsed_ms`；语义方案的 `average_latency_ms` 使用预计算向量，不是线上端到端延迟。此处尚没有真实语义模型成绩。

## 目录结构

```text
backend/        FastAPI 应用和后续领域服务
frontend/       中文工作台静态页面和浏览器测试
data/           示例数据和被 Git 忽略的运行数据
docs/           系统架构与项目路线图
tests/          自动化测试
```

进一步阅读：

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)：中文功能总览、逐文件职责、请求调用链、测试说明；今天先读 Day 19 的 DeepSeek 真调用记录与阅读指导；
- [`docs/ROADMAP.md`](docs/ROADMAP.md)：功能里程碑和完成标准。

## 项目原则

每个功能都必须能够演示、能够自动化验证，并对应真实测量结果。模型生成内容必须区分文档证据与模型推断，涉及设备安全的操作始终由人类确认。
