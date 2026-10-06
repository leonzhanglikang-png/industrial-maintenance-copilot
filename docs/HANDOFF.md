# 技术收尾交接

更新：2026-10-06。这是用户要求的续接说明，不是额外学习日志。用户授权完成技术主体、`ssh tencent` 部署与少量付费测试；443 已由用户放行。继续前核对状态，不重复付费调用或重做部署。

## 已核对

- 本地项目：`/Users/kang/简历项目agent`，功能提交 `ed59fc5` 已推送 main；[CI 37454801797](https://github.com/leonzhanglikang-png/industrial-maintenance-copilot/actions/runs/37454801797) 实际通过 303 项 Python、5 项浏览器、Ruff 和 Docker/重启验证。
- DeepSeek 回答已接通：本机 `.env` 为 `chat_completions`、`deepseek-flash`、输出上限 512；此前 3 次真实调用共 1489 token。密钥只在 `.env`，不要输出、提交或写进本文。
- Embedding 没有独立 API 密钥，已新增 `LocalSemanticEmbeddingProvider`（可选 `semantic` extra），384 维多语言 MiniLM 量化 CPU 模型。固定版本 `faf4aa4225822f3bc6376869cb1164e8e3feedd0` 已下载至本机 `data/models/minilm`，模型不进入 Git。
- 本机真实验证：中文/英文泵低压余弦相似度 0.8467，无关文本 0.1747；60 题未审核合成基准的语义向量 Recall@5=97.5%、语义 RRF=100%、MRR@5=0.9583。`data/processed/semantic-acceptance.json` 保留实际报告。普通 Pytest 强制离线哈希，不下载权重。
- 服务器：`ssh tencent` → `ubuntu@124.221.234.13`，4 CPU、3723 MiB RAM；加载模型后本项目约 728 MiB，机器约 1.9 GB 可用。不是负载容量测试。
- 已有应用 `/home/ubuntu/zero-to-tech`：Nginx 80 端口，`zero-to-tech-backend.service` 使用 8000。必须保留其目录、配置和运行状态。
- 本项目已部署 `/home/ubuntu/industrial-maintenance-copilot`、回环端口 8010、`maintenance-copilot.service`；独立 `.venv` 安装锁定的运行＋semantic 依赖。模型文件全部到位，权重/大分词文件通过 SHA256。没有 Docker，使用 systemd。
- [https://124.221.234.13/](https://124.221.234.13/) 已实际 HTTP 200、TLS 校验成功；未认证业务请求 401。公网上传英文合成手册、中文首条来源正确、离线带引用回答/拒答、三工具 Agent 与服务重启后数据恢复均通过。实际记录为本机 `data/processed/deployment-acceptance.json`。
- Nginx 独立 443 配置及 Let's Encrypt IP 证书已安装；当前证书到期 2026-10-13，`copilot-certificate-renew.timer` 每日两次检查续期，模拟续期成功。服务/timer 均 active/enabled；未重启整机。原 HTTP 网站仍 200、原后端 active。
- 服务器配置 `.env` 权限 600，`ANSWER_GENERATOR=extractive`，`EMBEDDING_PROVIDER=local`，访问口令随机生成、限流 20/min。本机口令文件 `data/processed/tencent-access.txt` 权限 600，禁止输出/提交。模型 API Key 不是访问口令。

## 唯一部署授权停点

自动审批拒绝了 DeepSeek 密钥传输，原因是缺少对该目的地的明确敏感凭据授权。确认卡片已询问用户“允许传到 tencent 服务器 / 不传密钥，公网先使用离线回答”。目前未取得单独答复，服务器没有该密钥；“已添加”指防火墙 443，不能视为密钥传输授权。不得绕过拒绝。

取得用户明确授权后的步骤：

1. 在明确说明密钥与 `tencent` 目的地的升级审批命令中，将本机 `.env` 的模型配置通过 SSH 安全传输至服务器 `.env`，权限 600；不得输出或提交密钥。
2. 只重启 `maintenance-copilot.service`；公网 `/app-config` 确认为 `chat_completions`。本次额外付费验收最多 3 个短输出请求：有引用中文回答、缺证据拒答、三工具 Agent；保持 512 token、SDK 重试 0。记录实际请求数量/结果，不把离线记录说成 DeepSeek。
3. 更新现有 README/架构/路线图的授权状态和实际结果，中文提交并用 leonzhanglikang-png 身份推送；不要全局切换 GitHub 账户。

若用户选择不传密钥，保留已验收的离线公网模式。中文跨语言检索已验证，离线摘录器按词匹配，不负责跨语言答案生成。

临时工具目录 `/private/tmp/copilot-technical.kpGr1e`：`configure.py --offline` 已用于无模型密钥部署；无 `--offline` 时只在取得单独授权后运行。它生成被 Git 忽略的 `data/processed/tencent.env`（当前无模型密钥）并复用访问口令。`accept_deployment.py` 验证无付费公网链路，`--restart-check` 只验证恢复，不发模型请求。临时目录可能被系统清理，必要时根据现有配置重建，不依赖它作为长期部署机制。

## 运维注意

- 运行环境 Python 3.12，uv 位于 `/home/ubuntu/.local/share/copilot-tools/bin/uv`，Certbot 位于 `/opt/copilot-certbot/bin/certbot`。依赖通过腾讯云 PyPI 镜像加 `--require-hashes` 安装，版本来自仓库锁文件；远端 `deploy/requirements.lock.txt` 为生成文件。
- 可复用配置在仓库 `deploy/`。Nginx 实际配置 `/etc/nginx/sites-available/maintenance-copilot`；证书 `/etc/letsencrypt/live/maintenance-copilot/`。不要复制私钥或覆盖原网站配置。
- 当前 Docker/Compose 是默认哈希/远程模式，没有安装 semantic extra 或挂载本地权重；不要把 systemd 的实测结果称为语义 Docker 验收。
- GitHub 全局活动用户可能仍是 lzha0323-art。推送使用单命令 `GH_TOKEN="$(gh auth token --user leonzhanglikang-png)" git -c credential.helper= -c 'credential.helper=!gh auth git-credential' push origin main`，不要打印 token。

真实检索质量、人工审核的独立评测集及最终求职材料属于后续验收。本次只推进用户指定的技术主体。
