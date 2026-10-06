# 技术收尾交接

更新：2026-10-06。这是用户要求的续接说明，不是额外学习日志。技术部署主体已完成；用户已单独允许将 DeepSeek 密钥传到 `tencent`，443 已由用户放行。继续前核对状态，不重复付费调用或重做部署。

## 已核对

- 本地项目：`/Users/kang/简历项目agent`，功能提交 `ed59fc5` 已推送 main；[CI 37454801797](https://github.com/leonzhanglikang-png/industrial-maintenance-copilot/actions/runs/37454801797) 实际通过 303 项 Python、5 项浏览器、Ruff 和 Docker/重启验证。
- DeepSeek 本机及服务器均为 `chat_completions`、`deepseek-flash`、输出上限 512、SDK 重试 0；此前本机 3 次真实调用共 1489 token，本轮新增 3 次公网真调用全部通过。配置文件权限 600，禁止输出/提交密钥。
- Embedding 没有独立 API 密钥，已新增 `LocalSemanticEmbeddingProvider`（可选 `semantic` extra），384 维多语言 MiniLM 量化 CPU 模型。固定版本 `faf4aa4225822f3bc6376869cb1164e8e3feedd0` 已下载至本机 `data/models/minilm`，模型不进入 Git。
- 本机真实验证：中文/英文泵低压余弦相似度 0.8467，无关文本 0.1747；60 题未审核合成基准的语义向量 Recall@5=97.5%、语义 RRF=100%、MRR@5=0.9583。`data/processed/semantic-acceptance.json` 保留实际报告。普通 Pytest 强制离线哈希，不下载权重。
- 服务器：`ssh tencent` → `ubuntu@124.221.234.13`，4 CPU、3723 MiB RAM；加载模型后本项目约 728 MiB，机器约 1.9 GB 可用。不是负载容量测试。
- 已有应用 `/home/ubuntu/zero-to-tech`：Nginx 80 端口，`zero-to-tech-backend.service` 使用 8000。必须保留其目录、配置和运行状态。
- 本项目已部署 `/home/ubuntu/industrial-maintenance-copilot`、回环端口 8010、`maintenance-copilot.service`；独立 `.venv` 安装锁定的运行＋semantic 依赖。模型文件全部到位，权重/大分词文件通过 SHA256。没有 Docker，使用 systemd。
- [https://124.221.234.13/](https://124.221.234.13/) 已实际 HTTP 200、TLS 校验成功；未认证业务请求 401。公网上传英文合成手册、中文首条来源正确、离线带引用回答/拒答、三工具 Agent 与服务重启后数据恢复均通过。实际记录为本机 `data/processed/deployment-acceptance.json`。
- Nginx 独立 443 配置及 Let's Encrypt IP 证书已安装；当前证书到期 2026-10-13，`copilot-certificate-renew.timer` 每日两次检查续期，模拟续期成功。服务/timer 均 active/enabled；未重启整机。原 HTTP 网站仍 200、原后端 active。
- 服务器配置 `.env` 权限 600，`ANSWER_GENERATOR=chat_completions`，`EMBEDDING_PROVIDER=local`，访问口令随机生成、限流 20/min。本机口令文件 `data/processed/tencent-access.txt` 权限 600，禁止输出/提交。模型 API Key 不是访问口令。

## 授权停点已解除

首次自动审批因授权不足拒绝了密钥传输；之后用户对“将本机 DeepSeek Key 经 SSH 传到 tencent（124.221.234.13）供后端读取”明确回复“允许”。据此通过加密 SSH 传输、保持 600 权限并只重启本项目，未绕过审批。

已完成的 3 次公网付费验收：

1. 中文压缩机启动检查项：HTTP 200、中文回答、有效合成手册引用，6.98 秒。
2. 未提供轴零件号/扭矩：HTTP 200、固定拒答、无引用，1.10 秒。
3. 中文泵低压＋历史＋示例温度：HTTP 200、有效泵手册引用、三步 succeeded/completed，1.37 秒。

结果及预先保存的调用计数位于本机 `data/processed/tencent-deepseek-acceptance.json`；三次之后已停止，不得因接续而重复收费测试。公网 API 没有 token 计数，不声称已知账单金额；首条包含冷加载，不是负载 P95。独立质量/成本/并发与求职材料属于后续工作，不是部署授权阻塞。

临时工具目录 `/private/tmp/copilot-technical.kpGr1e`：`configure.py` 已按授权生成并传输模型配置；本机被忽略的 `data/processed/tencent.env` 当前含密钥，权限 600，不得打印。`accept_deepseek_public.py` 的 3 请求限额已耗尽；`accept_deployment.py --restart-check` 只查鉴权、文档和检索，不发付费模型请求。临时目录可能被系统清理，不能作为长期部署机制。

## 运维注意

- 运行环境 Python 3.12，uv 位于 `/home/ubuntu/.local/share/copilot-tools/bin/uv`，Certbot 位于 `/opt/copilot-certbot/bin/certbot`。依赖通过腾讯云 PyPI 镜像加 `--require-hashes` 安装，版本来自仓库锁文件；远端 `deploy/requirements.lock.txt` 为生成文件。
- 可复用配置在仓库 `deploy/`。Nginx 实际配置 `/etc/nginx/sites-available/maintenance-copilot`；证书 `/etc/letsencrypt/live/maintenance-copilot/`。不要复制私钥或覆盖原网站配置。
- 当前 Docker/Compose 是默认哈希/远程模式，没有安装 semantic extra 或挂载本地权重；不要把 systemd 的实测结果称为语义 Docker 验收。
- 公网问答/Agent 现在会调用 DeepSeek，原文检索只使用 CPU。需暂停付费时改服务器 `ANSWER_GENERATOR=extractive` 并只重启本项目；不要删除用户密钥或上传库。
- GitHub 全局活动用户可能仍是 lzha0323-art。推送使用单命令 `GH_TOKEN="$(gh auth token --user leonzhanglikang-png)" git -c credential.helper= -c 'credential.helper=!gh auth git-credential' push origin main`，不要打印 token。

真实检索质量、人工审核的独立评测集及最终求职材料属于后续验收。本次只推进用户指定的技术主体。
