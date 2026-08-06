# 工业设备智能运维助手

这是一个面向求职展示的完整 AI 应用项目，将检索增强生成（RAG）、工具型 Agent、后端工程、离线评测和部署结合在工业设备维护场景中。

## 要解决的问题

维护工程师需要同时查阅设备手册、历史故障记录和传感器数据。普通聊天机器人可能给出缺少证据的建议，因此本项目强调来源引用、工具执行记录和人工确认。

目标用户是负责联网工业设备的维护工程师。系统提供检索和检查建议，但不会直接控制真实设备或替代安全关键决策。

## 当前已实现

- FastAPI 应用工厂和环境配置；
- `GET /api/v1/health` 健康检查接口；
- `GET /api/v1/info` 项目信息接口；
- Pydantic 响应 Schema；
- Pytest 接口测试和 Ruff 代码检查。

当前处于 Milestone 1：定义文档与文本块模型，为文档导入和基础检索建立数据结构。

## 计划实现

1. 导入 PDF、Markdown 和纯文本设备资料；
2. 使用向量检索与关键词检索查找相关证据；
3. 对检索结果重排序并保留来源和页码；
4. 查询历史故障记录并分析传感器数据；
5. 通过受约束的 Agent 生成检查建议和工具轨迹；
6. 建立离线评测、日志、容器化和线上部署。

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
- API 文档：`http://127.0.0.1:8000/docs`

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
