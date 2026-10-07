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
- 已实测的本地 CPU 多语言语义向量（384 维 MiniLM），以及可选 OpenAI 兼容远程向量适配器；
- 基于 Reciprocal Rank Fusion（RRF）的排名融合；
- 基于查询词覆盖率的轻量候选重排；
- 可拒答的证据摘录生成器，以及经过检索候选校验的 `[S1]` 引用；
- 可显式启用的 OpenAI Responses 回答生成器，无引用或越界引用会被拒绝；
- Chat Completions 回答适配器，DeepSeek 本机和公网分别完成 3 次授权真调用，保留引用校验、输出上限和安全失败处理；
- 只读的历史故障查询和传感器区间分析工具；
- 最多执行三步、返回完整工具轨迹的确定性策略 Agent；
- Agent 工具异常时立即停止，保留已完成步骤与引用，并在工作台显示失败步骤；
- 中文演示工作台：上传、原文检索、引用问答和三工具综合分析；
- SQLite 文本块持久化，重启后重建混合索引，并提供文档列表；
- 手册删除与索引同步清理，记录删除状态以避免内置手册重启后重新出现；
- 故障记录录入、按设备编号查询及 SQLite 持久化，演示历史单独标识；
- 模型正文与引用列表统一编号，模型故障和引用错误返回明确状态码；
- 可配置共享访问口令、进程内限流、请求编号和 JSON 请求日志；
- 非 root Docker 镜像、持久卷，以及 GitHub CI 容器与浏览器测试；
- 腾讯云独立 systemd 服务、公网 HTTPS 和自动证书续期；
- 可复现的 Recall@K、MRR 和平均延迟离线评测；
- 独立的 60 题合成检索基准、来源与标注校验、逐题命中和漏检诊断（尚待人工审核）；
- Pytest 自动化测试和 Ruff 代码质量检查。

当前已实现 RAG/Agent 技术演示主体，并部署到 [公网工作台](https://124.221.234.13/)。服务器使用真实本地语义向量与 DeepSeek 回答，中文问答、引用、拒答和三步 Agent 已实测。2026-10-07 新增公开 DOE 手册测试集草案、60 次真实模型回答与费用上界记录、本地 HTTP 负载报告和求职材料；人工质量审核与真实维修人员验收仍未完成。详见 [评测与限制](docs/EVALUATION.md) 和 [项目简历说明](docs/PORTFOLIO.md)。

2026-10-07 本地验证：**313 项 Python 测试、8 项浏览器功能回归、独立演示录制测试通过**。60 次 DeepSeek 真实评测输入 52,837 token、输出 3,502 token，按高峰未命中价格保守核算费用上界 0.133690 元；10 道缺证据题拒答，50 道可回答题中有 11 道中文题拒答。标签未人工确认，不能把这些数字写成答案正确率。功能提交 `41e7d17` 的 [CI 37588276119](https://github.com/leonzhanglikang-png/industrial-maintenance-copilot/actions/runs/37588276119) 已通过相同测试及 Docker/重启检查，同一功能版本已更新公网。

2026-10-06 验收：代码提交 `ed59fc5` 的 **303 项 Python 测试、5 项浏览器测试、Ruff、Docker 构建及重启持久化检查全部通过**，见[本次 CI 记录](https://github.com/leonzhanglikang-png/industrial-maintenance-copilot/actions/runs/37454801797)。CI 不调用付费模型、不下载权重；另行完成本地真实语义模型与公网链路验证。本机此前 3 次 DeepSeek 真调用共 1489 token；取得服务器密钥传输授权后，新增 3 次公网真调用全部通过，未继续付费测试。公网 API 不返回 token 使用量，实际费用以服务商账单为准。

默认演示使用确定性哈希向量和证据摘录式回答生成器，目的是在不依赖外部模型的情况下验证完整 RAG/Agent 链路。设置 `ANSWER_GENERATOR=openai` 后可改用 Responses API，但没有密钥也能运行全部离线功能。哈希向量不能被等同于语义 Embedding；旧 6 题上四方案的 Recall/MRR 相同，新增 60 题未审核合成基准上 BM25 的 Recall@5 为 100%，当前混合重排为 96.67%，不能声称混合方案优于 BM25 或代表生产质量。

## 计划实现

1. 人工审核已固定的独立测试集草案及真实回答，继续公平比较已经实测的语义方案；
2. 扩展回答质量评测、Agent 失败后的恢复策略和工具结果综合推理（DeepSeek 小样本真调用已验证）；
3. 真实用户验收及公网模型负载验证；如需规模扩展，再迁移到 PostgreSQL/Qdrant。

## 本地运行

```bash
test -f .env || cp .env.example .env
UV_CACHE_DIR=.uv-cache uv sync --frozen
UV_CACHE_DIR=.uv-cache uv run python -m pytest
UV_CACHE_DIR=.uv-cache uv run uvicorn backend.app.main:app --reload --no-access-log
```

启动后访问：

- 运维分析：`http://127.0.0.1:8000/`
- 文档知识库：`http://127.0.0.1:8000/knowledge`
- 健康检查：`http://127.0.0.1:8000/api/v1/health`
- 项目信息：`http://127.0.0.1:8000/api/v1/info`
- 文档上传：`POST http://127.0.0.1:8000/api/v1/documents/upload`
- 文档列表：`GET http://127.0.0.1:8000/api/v1/documents`
- 混合检索：`POST http://127.0.0.1:8000/api/v1/search`
- 引用回答：`POST http://127.0.0.1:8000/api/v1/answers`
- Agent 工作流：`POST http://127.0.0.1:8000/api/v1/agent/runs`
- API 文档：`http://127.0.0.1:8000/docs`

侧栏切换两页时保留问题、分析结果和当前内存中的访问口令；刷新页面后需要重新输入口令。

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

向量模型与回答模型独立配置。没有独立向量 API 密钥时，使用已实测的本地 CPU 模型，不占用 DeepSeek 调用额度。先安装可选依赖并下载固定版本的公开模型（约 255 MiB，文件被 Git 忽略）：

```bash
UV_CACHE_DIR=.uv-cache uv sync --frozen --extra semantic
UV_CACHE_DIR=.uv-cache uv run --extra semantic python -c 'from huggingface_hub import snapshot_download; from backend.app.infrastructure.local_embeddings import MODEL_REPOSITORY, MODEL_REVISION; snapshot_download(MODEL_REPOSITORY, revision=MODEL_REVISION, local_dir="data/models/minilm")'
```

本机 `.env` 配置如下，然后用 `uv run --extra semantic uvicorn backend.app.main:app --reload --no-access-log` 启动：

```dotenv
EMBEDDING_PROVIDER=local
EMBEDDING_LOCAL_PATH=data/models/minilm
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
EMBEDDING_DIMENSION=384
```

本地模式只读取已有文件，不在服务运行时自动下载。CPU 推理不调用付费向量 API，但占用服务器资源。相对路径按项目根目录解析；模型固定在适配器中，不支持仅修改模型名就加载任意权重。本次模型来自 [Qdrant 发布的量化 ONNX 仓库](https://huggingface.co/Qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q)，版本与下载逻辑见源码。

如需远程向量服务，只编辑本机 `.env`，不要提交密钥；远程模式可能计费：

```dotenv
EMBEDDING_PROVIDER=openai
EMBEDDING_BASE_URL=https://api.openai.com/v1
EMBEDDING_API_KEY=your-local-embedding-key
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSION=1536
EMBEDDING_TIMEOUT_SECONDS=30
```

修改后重启服务。默认仍是 `EMBEDDING_PROVIDER=hash`，无需密钥。上述模型的默认输出为 1536 维，接口使用 `encoding_format="float"`，依据 [OpenAI 官方文档](https://developers.openai.com/api/docs/guides/embeddings)。`EMBEDDING_DIMENSION` 只校验模型输出，不请求降维；使用兼容服务时，需要按其模型填写地址、名称与原生维度，兼容性须实测。

远程模式会将文档块和查询发送到配置的模型服务，不要上传未经许可的资料。当前 SQLite 只保存文本，启动和语料变化时重新生成向量；大语料的缓存与增量优化尚未实现。模型错误不会自动回退哈希，API 返回安全的 503。远程 Embedding 仍只有模拟 HTTP 验证；本地语义模型已经实测，两者不要混称。

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

打开 `http://127.0.0.1:8000/`，输入同一个访问口令。Compose 默认只监听本机端口，使用命名卷保留 SQLite 数据。`docker compose down` 保留卷；不要在需要保留知识库时使用 `down -v`。现有镜像未安装 `semantic` extra、Compose 未挂载本地模型，不能直接用它运行本地语义模式；本次腾讯云部署使用下面的 systemd 方案。

### 已上线的腾讯云服务

- 入口：[https://124.221.234.13/](https://124.221.234.13/)，业务接口需要共享访问口令；本机口令文件为 `data/processed/tencent-access.txt`，不要提交或公开它，也不要在页面输入模型 API Key。
- 项目目录 `/home/ubuntu/industrial-maintenance-copilot`；`maintenance-copilot.service` 单进程监听 `127.0.0.1:8010`，Nginx 通过 443 转发。原有 80/8000 网站保留。
- 使用受信任的 Let's Encrypt IP 证书；短期证书由 `copilot-certificate-renew.timer` 每日两次检查续期。证书续期模拟测试已通过，服务和 timer 已启用开机启动；没有重启整台服务器。
- 已实际验证 HTTPS、未认证 401、公网上传后中文检索、服务重启后数据恢复；进一步通过真实 DeepSeek 验证中文引用回答、缺证据拒答及三工具 Agent。密钥经用户单独授权通过 SSH 传输，服务器 `.env` 权限为 600；未输出、进入页面或加入 Git。
- 公网问答和 Agent 的知识步骤现在会调用付费 DeepSeek 服务；只做原文检索不调用聊天模型。需要暂停模型费用时将服务器 `ANSWER_GENERATOR=extractive` 后重启本项目，语义向量仍在本地 CPU 运行。
- 运维命令：`ssh tencent 'systemctl status maintenance-copilot.service'`；查看请求日志用 `journalctl -u maintenance-copilot.service`；只重启本项目用 `sudo systemctl restart maintenance-copilot.service`。可复用的配置在 `deploy/`，不要覆盖原网站配置。

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

配置好本地或远程向量后，显式添加 `--include-semantic` 可增加语义向量、语义混合、语义混合重排三组对比；本地模式需要保留 `--extra semantic`：

```bash
UV_CACHE_DIR=.uv-cache uv run --extra semantic python -m backend.app.cli.evaluate_retrieval --dataset data/evaluation/maintenance_benchmark.json --include-semantic --details
```

本地模式使用本机 CPU，远程模式向服务发送基准语料与问题并可能计费；不带此开关始终只测原来的四组离线方案。60 题基准的 80 条唯一文本只批量嵌入一次，并复用于不同 K 和算法。报告单列 `embedding_elapsed_ms`；语义方案的 `average_latency_ms` 使用预计算向量，不是线上端到端延迟。本次真实本地模型 Recall@5 为 97.5%，语义 RRF 为 100%；标签仍未经人工审核，不代表独立测试或生产正确率，完整比较见架构说明顶部。

## 目录结构

```text
backend/        FastAPI 应用和后续领域服务
frontend/       中文工作台静态页面和浏览器测试
data/           示例数据和被 Git 忽略的运行数据
docs/           系统架构与项目路线图
deploy/         本次公网服务、HTTPS 和证书续期配置
tests/          自动化测试
```

进一步阅读：

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)：中文功能总览、逐文件职责、请求调用链、测试说明；今天先读 Day 20 的真实语义向量与部署阅读指导；
- [`docs/ROADMAP.md`](docs/ROADMAP.md)：功能里程碑和完成标准。

## 项目原则

每个功能都必须能够演示、能够自动化验证，并对应真实测量结果。模型生成内容必须区分文档证据与模型推断，涉及设备安全的操作始终由人类确认。
