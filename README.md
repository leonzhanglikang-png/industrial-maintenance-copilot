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
- 可复现的 Recall@K、MRR 和平均延迟离线评测；
- Pytest 自动化测试和 Ruff 代码质量检查。

当前已经完成 Milestone 3 的可演示纵向功能；Milestone 2 的评测集扩充和真实质量提升仍未完成。

默认演示使用确定性哈希向量和证据摘录式回答生成器，目的是在不依赖外部模型的情况下验证完整 RAG/Agent 链路。设置 `ANSWER_GENERATOR=openai` 后可改用 Responses API，但没有密钥也能运行全部离线功能。哈希向量不能被等同于语义 Embedding；现有 6 条小型评测集上四种检索方案的 Recall/MRR 暂时相同，因此尚不能声称混合检索带来了质量提升。

## 计划实现

1. 扩充检索评测集并接入真实语义 Embedding；
2. 增加持久化存储、演示界面和结构化日志；
3. 完成容器化、CI、线上部署和求职材料。

## 本地运行

```bash
cp .env.example .env
UV_CACHE_DIR=.uv-cache uv sync
UV_CACHE_DIR=.uv-cache uv run pytest
UV_CACHE_DIR=.uv-cache uv run uvicorn backend.app.main:app --reload
```

启动后访问：

- 健康检查：`http://127.0.0.1:8000/api/v1/health`
- 项目信息：`http://127.0.0.1:8000/api/v1/info`
- 文档上传：`POST http://127.0.0.1:8000/api/v1/documents/upload`
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

运行四组检索基线评测：

```bash
UV_CACHE_DIR=.uv-cache uv run python -m backend.app.cli.evaluate_retrieval
```

## 目录结构

```text
backend/        FastAPI 应用和后续领域服务
data/           示例数据和被 Git 忽略的运行数据
docs/           系统架构与项目路线图
tests/          自动化测试
```

进一步阅读：

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)：系统结构和关键技术取舍；
- [`docs/ROADMAP.md`](docs/ROADMAP.md)：功能里程碑和完成标准。

## 项目原则

每个功能都必须能够演示、能够自动化验证，并对应真实测量结果。模型生成内容必须区分文档证据与模型推断，涉及设备安全的操作始终由人类确认。
