# 2026-10-07 项目评测与证据

## 结论与限制

已完成可复现的检索对比、60 次真实 DeepSeek 回答记录、费用上界统计及本地 HTTP 小规模负载测试。**人工审核完成数为 0/60，答案正确率和逐句证据支持率暂不报告。** 这份报告不是生产 SLA、真实企业维修成效或领域专家验收。

## 固定测试资料

- 来源：美国能源部 [DOE-HDBK-1018/1-93 Mechanical Science Volume 1](https://www.osti.gov/servlets/purl/10154822)，美国联邦政府公开技术手册。采用泵章节的 25 段原文，保留 OCR 拼写，仅归一化空白；物理 PDF 页码可追溯。原文件 SHA256 在数据集内。
- [固定数据集](../data/evaluation/manual_holdout.json)：50 道可回答题是 **25 个主题的中英配对**，另外 10 道为缺失证据题。配对题有相关性，不能说成 50 个独立设备场景。题目、答案要点及相关性标签由 AI 起草，尚未经独立人员审核。
- 新资料与原 60 题合成开发集分离，在首次跑分前固定，没有用本次分数调参或更改线上检索策略。候选段落是预选原文，检索评测不覆盖 PDF 解析与自动切块；本地 HTTP 压测另经过实际 Markdown 解析切块。
- 本轮数据集 SHA256：`f18f557e5e35188c7efee11b50db1ab568f393d4b4e2f74306280058372f9a9c`。未来修订标签应另建版本，保留本次报告。

## 检索对比（未审核标签上的开发诊断）

所有方案使用相同语料、问题与 K。语义方案复用预计算向量，因此检索报告中的耗时不包含在线查询编码。

| 方案 | Recall@5 | MRR@5 |
|---|---:|---:|
| deterministic-hash-embedding | 46.00% | 0.2897 |
| bm25-keyword | 60.00% | 0.4923 |
| rrf-hybrid | 58.00% | 0.4313 |
| rrf-hybrid-token-overlap-reranked | 58.00% | 0.5000 |
| semantic-embedding | 78.00% | 0.6557 |
| semantic-rrf-hybrid | 68.00% | 0.5770 |
| semantic-rrf-hybrid-token-overlap-reranked | 70.00% | 0.5953 |

本轮纯语义检索 Recall@5=78%，当前语义混合＋重排=70%，BM25=60%。这提示多语言融合策略需要进一步分析；不能声称混合检索稳定优于纯语义，也不应拿未审核小样本直接选择生产策略。逐题命中与漏检见 [完整检索报告](evaluation/retrieval-2026-10-07.json)。

## 真实模型、拒答行为与费用

测试在本机进程内调用实际 RAG 服务，使用本地 MiniLM、当前语义混合＋重排及 DeepSeek `deepseek-flash`；不是公网 HTTP 并发验收。禁用思考，输出上限 512 token，SDK 重试 0。

- 用户授权最多 60 次、预算 5 元；实际 **60 次**，全部返回可解析结果，无额外付费重试。输入 **52,837 token**，输出 **3,502 token**。
- 使用核对过的 [DeepSeek 官方价格](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)：以高峰、全部输入缓存未命中的单价（输入 2 元/百万，输出 8 元/百万）保守核算，费用上界 **0.133690 元**。这是上界，不是账单实扣；缓存命中和空闲时段可能更低。调用前按 UTF-8 字节上界及全部候选资料预留 **2.174682 元**，低于 5 元后才发起请求。
- 本批串行调用耗时中位数约 **1.00 秒**，nearest-rank P95 约 **1.63 秒**；模型和索引已预加载，不能解释为冷启动或公网时延。
- 自动拒答检查：10/10 缺证据题拒答；50 道可回答题中 39 道带引用回答，11 道中文题拒答。按草案标签，拒答行为匹配为 49/60。这个指标不是答案正确率；带合法引用也不等于所有结论受证据支持。
- 11 个待排查案例：volute-zh, double-volute-zh, wear-zh, wearing-rings-zh, lantern-ring-zh, mechanical-seal-zh, suction-pressure-zh, suction-losses-zh, required-npsh-zh, recirculation-zh, pd-relief-zh。检索漏检、重排和生成保守性都可能影响结果，尚未完成因果归因。
- [完整回答与 usage](evaluation/deepseek-2026-10-07.json)、[逐次调用记录](evaluation/deepseek-2026-10-07.jsonl)。到达 60 次后停止付费评测。

## 人工审核方法

打开 [审核表 CSV](evaluation/deepseek-2026-10-07.review.csv)。每行已带问题、原文页码和候选证据、参考要点、实际回答、自动拒答状态。请由项目作者或熟悉设备的人逐项核对；如果仅由作者审核，应写明“作者审核”，不能称为独立专家。

1. `labels_approved`：确认相关原文、参考要点及应答/拒答标签是否正确，填写 `yes` 或 `no`。
2. `answer_correct`：回答是否正确、覆盖所问问题。拒答是否符合证据实际情况。
3. `all_claims_supported`：每一项事实是否有证据支持；填 `yes`/`no`。不要因为有 S1 就直接通过。
4. `reviewer`：真实审核者姓名或标识；`notes`：漏检、过度拒答、事实错误、标签问题等。
5. 发现草案标签错误时保留 `no` 和说明，修改标签后另建数据集版本；不要覆盖旧分数。

审核表绑定数据集和回答报告哈希，防止混用旧模型结果。汇总命令：

```bash
uv run python -m backend.app.cli.evaluate_answers \
  --output docs/evaluation/deepseek-2026-10-07.json \
  --review-csv docs/evaluation/deepseek-2026-10-07.review.csv
```

未填写真实审核者及合格标签的行不会计入人工质量分数。当前汇总为 `pending_human_review`，正确率为 `null`。

## 本地 HTTP 负载

环境：`macOS-26.6.2-arm64-arm-64bit-Mach-O`，Python `3.14.6`，单 Uvicorn 进程、本地 CPU MiniLM、离线摘录回答、2 份文档/64 块。客户端与服务端同机；每组只有 30 请求，没有持续压测或生产容量外推。首次搜索 **1361.6 ms**，包含模型/索引冷加载。

| 接口 | 并发 | 成功 | 热请求 P50 ms | 热请求 P95 ms | 成功请求/秒 |
|---|---:|---:|---:|---:|---:|
| /search | 1 | 30/30 | 6.07 | 6.82 | 162.0 |
| /search | 5 | 30/30 | 24.62 | 26.28 | 197.7 |
| /search | 10 | 30/30 | 49.64 | 51.73 | 190.0 |
| /answers | 1 | 30/30 | 6.65 | 7.85 | 146.0 |
| /answers | 5 | 30/30 | 26.43 | 29.09 | 181.5 |
| /answers | 10 | 30/30 | 54.78 | 60.85 | 174.2 |

两接口共 180 个热请求成功，另有 1 次冷搜索成功。限流在该隔离环境调高以测应用行为；不能解释为公网限流后的表现，也不能把离线摘录吞吐量当作 DeepSeek 吞吐量。完整状态分布和样本见 [HTTP 报告](evaluation/http-2026-10-07.json)。

## 复现

离线测试：`uv sync --frozen && uv run python -m pytest`；浏览器回归及容器重启流程在 GitHub CI 中执行，不消耗付费额度。

检索评测（需按 README 安装 semantic extra 和固定模型）：

```bash
uv run --extra semantic python -m backend.app.cli.evaluate_retrieval \
  --dataset data/evaluation/manual_holdout.json --include-semantic --details
```

真实回答评测必须先获得新的预算授权，再显式使用 `--allow-paid`，并提供新的输出路径；已有输出及调用日志存在时，程序拒绝重复运行。当前 60 次授权已用完。

HTTP 压测只接受关闭访问口令的隔离摘录服务，拒绝对远程回答模式进行未经授权的并发付费测试：

```bash
uv run python -m backend.app.cli.benchmark_http \
  --base-url http://127.0.0.1:8765 --output data/processed/http-run.json
```

## 尚未完成

人工相关性和回答质量审核、真实维修人员的独立可用性验收、多公司权限隔离、真实 IoT 接入、长期运行与公网大模型负载验证均未完成。
