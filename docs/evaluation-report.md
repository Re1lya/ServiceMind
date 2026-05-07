# ServiceMind 阶段验证与评估结果记录

## 1. 文档目标

本文档用于沉淀 ServiceMind 的阶段性效果验证计划、检索召回数据、回答质量评估结果和后续优化记录。

它不是一次性的测试报告，而是每次调整 `RAG / Prompt / Agent / Tool` 链路后都要更新的评估台账，用来回答四个问题：

1. 这次改动验证了哪个阶段能力？
2. 使用了哪一批固定测试问题？
3. 召回、回答、工具调用指标有没有变化？
4. 新增风险和下一步边界是什么？

## 2. MVP 整体与验证边界

ServiceMind MVP 当前主线是：

`前端客服工作台 -> FastAPI API 层 -> Agent 编排 -> RAG 检索 / 工具调用 -> 大模型生成 -> 统一响应 -> 日志追踪`

当前项目已经具备线上应用链路的基础形态，后续需要补齐两条工程化能力：

- `离线数据处理链路`：把 FAQ、售后政策、商品规则、订单/物流说明等原始资料批量清洗、切分、向量化并写入索引。
- `阶段效果验证链路`：用固定问题集对比不同检索、Prompt、Agent 策略，记录 Recall@K、Hit@1、回答可依据率、工具调用正确率等指标。

## 3. 阶段验证安排

| 阶段 | 验证对象 | 实现范围 | 核心指标 | 通过标准 |
|---|---|---|---|---|
| S0 | 当前 Baseline | FAISS 向量召回 + 词法回退 + 来源返回 | Hit@1、Recall@3、来源是否返回 | FAQ 样例问题能命中正确来源 |
| S1 | 离线索引构建 | 批量读取 `data/raw`，清洗、切分、embedding、写入 FAISS | 文档数、chunk 数、失败数、处理耗时 | 可重复构建索引并生成处理报告 |
| S2 | 固定检索评估 | 使用 `data/eval/retrieval_questions.json` 跑固定问题集 | Hit@1、Recall@3、Recall@5、MRR | 指标可复现，结果可对比 |
| S3 | 混合检索增强 | 向量召回 + BM25/关键词召回 | 关键词类问题 Recall@5 | 不降低 Baseline 的前提下提升关键词问题命中 |
| S4 | Prompt/回答验证 | 验证回答是否引用来源、是否覆盖关键点 | 回答可依据率、关键词覆盖率、无依据内容比例 | 回答必须能回溯到检索来源或工具结果 |
| S5 | Agent 工具调用验证 | 订单、物流、投诉等工具选择与调用 | 工具选择正确率、调用成功率、兜底率 | 高频业务问题能稳定路由到正确工具 |

## 4. 建议数据集格式

检索评估问题建议放在 `data/eval/retrieval_questions.json`：

```json
[
  {
    "id": "faq_refund_001",
    "question": "七天无理由退款规则是什么？",
    "gold_doc_id": "refund_policy",
    "expected_keywords": ["七天无理由", "退款", "商品完好"],
    "category": "refund"
  }
]
```

回答评估问题建议放在 `data/eval/answer_questions.json`：

```json
[
  {
    "id": "answer_refund_001",
    "question": "商品已经拆封还能退吗？",
    "expected_source": "refund_policy",
    "expected_keywords": ["商品完好", "售后规则"],
    "must_not_include": ["一定可以退", "无需审核"]
  }
]
```

Agent 工具调用评估建议放在 `data/eval/tool_cases.json`：

```json
[
  {
    "id": "tool_logistics_001",
    "message": "帮我查一下订单 SM202605060001 到哪了",
    "expected_route": "logistics_query",
    "expected_tool": "logistics_query",
    "required_slots": ["order_id"]
  }
]
```

## 5. 指标定义

| 指标 | 说明 | 计算方式 |
|---|---|---|
| Hit@1 | 第一条召回结果是否是正确文档 | `top1.document_id == gold_doc_id` |
| Recall@K | 前 K 条结果是否包含正确文档 | `gold_doc_id in top_k.document_ids` |
| MRR | 正确文档排名越靠前分数越高 | `1 / rank(gold_doc_id)`，未命中为 0 |
| 来源返回率 | 回答是否带有可追溯来源 | `有 knowledge_sources 的回答数 / 总回答数` |
| 回答可依据率 | 回答关键结论是否来自来源片段或工具结果 | `可依据回答数 / 总回答数` |
| 工具选择正确率 | Agent 是否选择了预期工具 | `正确工具调用数 / 工具场景总数` |
| 格式正确率 | JSON 或结构化输出是否满足 schema | `格式合法输出数 / 总输出数` |
| 平均耗时 | 单次检索或回答平均延迟 | `总耗时 / 请求数` |

## 6. 当前召回快照

记录时间：`2026-05-06`

数据来源：

- 索引文件：`data/vector_store/servicemind.faiss`
- 元数据文件：`data/vector_store/metadata.json`
- 当前元数据文档数：`1`
- 当前样例文档：`退款规则`

当前 FAISS 原始召回结果如下。该结果只代表当前本地索引的最小 sanity check，不等价于完整 Recall@K 评估。

| Query | Rank | Document ID | Title | Score | Snippet | 判定 |
|---|---:|---|---|---:|---|---|
| 退款规则 | 1 | `doc_a4337d9ea77444d0a70c2f5b8af98d27` | 退款规则 | 0.218218 | 平台支持七天无理由退款，商品需要保持完好。 | 命中 |
| 七天无理由 | 1 | `doc_a4337d9ea77444d0a70c2f5b8af98d27` | 退款规则 | 0.487950 | 平台支持七天无理由退款，商品需要保持完好。 | 命中 |
| 商品完好 | 1 | `doc_a4337d9ea77444d0a70c2f5b8af98d27` | 退款规则 | 0.436436 | 平台支持七天无理由退款，商品需要保持完好。 | 命中 |
| 发票规则 | 1 | `doc_a4337d9ea77444d0a70c2f5b8af98d27` | 退款规则 | 0.000000 | 平台支持七天无理由退款，商品需要保持完好。 | 不相关，应在上层过滤或回退 |

当前观察：

- 与退款相关的 3 个样例查询均能召回 `退款规则`。
- `发票规则` 在 FAISS 原始搜索中返回了 0 分结果，说明后续评估脚本需要显式记录低分无效命中。
- 当前在线检索入口 `retrieve_documents()` 已对 `score > 0` 做过滤，并结合数据库 indexed 文档状态判断；正式评估应优先调用在线检索入口，而不是只调用底层 FAISS 搜索。

## 7. 当前评估状态

| 项目 | 状态 | 说明 |
|---|---|---|
| 固定检索评估集 | 已建立第一版 | 当前位于 `data/eval/retrieval_questions.json`，共 5 条样例 |
| `evaluate_retrieval.py` | 已实现 | 当前位于 `backend/scripts/evaluate_retrieval.py`，支持 Markdown/JSON 报告 |
| Baseline Recall@5 | 已统计 | 当前正样本 Recall@5 = 100.00%，但样本规模很小 |
| Baseline Hit@1 | 已统计 | 当前正样本 Hit@1 = 100.00%，但只有 1 个知识文档 |
| Baseline MRR | 已统计 | 当前正样本 MRR = 1.0000 |
| 回答可依据率 | 已统计两版 | 当前位于 `backend/scripts/evaluate_answer.py`，支持抽取式 baseline 与真实 `rag_llm` 模式 |
| 工具调用正确率 | 已统计第一版 | 当前位于 `backend/scripts/evaluate_tools.py`，覆盖订单和物流工具 |

## 8. 2026-05-06：Baseline RAG 检索评估

### 8.1 本次怎么测

评估目标：

- 验证当前 RAG 检索入口 `retrieve_documents()` 在固定问题集上的命中情况。
- 不只测 FAISS 原始搜索，而是测试当前线上链路使用的检索逻辑：`FAISS 向量召回 -> 低分或无效时回退轻量词法检索`。
- 同时放入负样本，检查系统是否会对知识库中不存在的问题误召回。

评估数据：

- 数据集：`data/eval/retrieval_questions.json`
- 样本数：`5`
- 正样本：`3` 条，均期望命中 `退款规则`
- 负样本：`2` 条，期望无命中，分别是 `发票规则` 和 `偏远地区物流`
- 当前知识库规模：`1` 个 FAISS metadata 文档，标题为 `退款规则`

运行命令：

```powershell
cd backend
.venv\Scripts\python.exe scripts\evaluate_retrieval.py --dataset ..\data\eval\retrieval_questions.json --report ..\data\reports\retrieval_eval_report.json --top-k 5 --source metadata
```

说明：

- `--source metadata` 表示脚本从当前 `data/vector_store/metadata.json` 创建临时 SQLite 评估库，再调用真实 `retrieve_documents()`。
- 本次输出报告为 `data/reports/retrieval_eval_report.json`。
- 这种方式适合当前 MVP 阶段快速评估本地 FAISS 索引；后续接入正式 MySQL 后，应使用 `--source database` 评估真实业务库。

### 8.2 本次实际数据

| 指标 | 结果 |
|---|---:|
| Total cases | 5 |
| Positive cases | 3 |
| Negative cases | 2 |
| Hit@1 | 100.00% |
| Recall@5 | 100.00% |
| MRR | 1.0000 |
| Negative no-hit accuracy | 50.00% |
| Keyword coverage | 61.11% |
| Average latency | 145.993 ms |

逐条结果：

| Case ID | Question | Expected | Top1 | Score | 结果 |
|---|---|---|---|---:|---|
| `faq_refund_001` | 退款规则是什么？ | 退款规则 | 退款规则 | 0.164957 | 命中 |
| `faq_refund_002` | 七天无理由退款需要满足什么条件？ | 退款规则 | 退款规则 | 0.507093 | 命中 |
| `faq_refund_003` | 商品保持完好还能不能退？ | 退款规则 | 退款规则 | 0.484182 | 命中 |
| `faq_invoice_negative_001` | 发票规则是什么？ | 无命中 | 退款规则 | 6.000000 | 误召回 |
| `faq_logistics_negative_001` | 偏远地区物流多久能送到？ | 无命中 | 无命中 | N/A | 正确拒召回 |

### 8.3 结论

当前 Baseline 在“知识库里确实存在退款规则”的正样本上表现正常：

- 正样本 `Hit@1 = 100.00%`
- 正样本 `Recall@5 = 100.00%`
- 正样本 `MRR = 1.0000`

但这个结果不能说明当前 RAG 已经足够好，原因是：

- 当前知识库只有 1 个文档，正样本都围绕 `退款规则`，评估难度很低。
- 负样本准确率只有 `50.00%`，说明系统存在误召回。
- `发票规则是什么？` 被召回到 `退款规则`，主要原因是轻量词法回退按中文单字匹配，`规则` 这类泛化词会把不相关文档拉上来。

### 8.4 后续改进方向

优先级从高到低：

1. 扩充评估集到 30-50 条，覆盖退款、发票、物流、售后、商品活动、会员权益等类别。
2. 给检索增加最低分阈值，尤其是词法回退结果，避免只因为命中 `规则` 这类泛词就返回答案。
3. 把中文词法回退从单字匹配升级为分词或 BM25，降低泛词误召回。
4. 为负样本建立 `no_answer / low_confidence` 兜底策略，前端提示“当前知识库未命中相关规则”。
5. 扩充知识库后重新跑 `evaluate_retrieval.py`，再比较 Hit@1、Recall@5、MRR 和负样本 no-hit accuracy。

## 9. 2026-05-06：扩充数据集后的检索优化对比

### 9.1 本次做了什么

本轮在上一版 5 条样例评估的基础上，补齐了更接近真实客服场景的知识库和检索问题集：

- 新增 `data/raw` 下 10 份客服知识文档，覆盖退款、发票、物流、会员、活动、维修、投诉、支付、优惠券、隐私账号。
- 扩充 `data/eval/retrieval_questions.json` 到 30 条。
- 其中正样本 27 条，负样本 3 条。
- 先跑扩充后的 baseline，再实现召回优化并复测。

重建索引命令：

```powershell
cd backend
.venv\Scripts\python.exe scripts\build_kb.py --input ..\data\raw --report ..\data\reports\kb_build_report.md --database-url sqlite:///../data/reports/retrieval_eval.sqlite --init-db
```

扩充后 baseline 命令：

```powershell
cd backend
.venv\Scripts\python.exe scripts\evaluate_retrieval.py --dataset ..\data\eval\retrieval_questions.json --report ..\data\reports\retrieval_eval_baseline_expanded.json --top-k 5 --source metadata
```

优化后复测命令：

```powershell
cd backend
.venv\Scripts\python.exe scripts\evaluate_retrieval.py --dataset ..\data\eval\retrieval_questions.json --report ..\data\reports\retrieval_eval_optimized.json --top-k 5 --source metadata
```

### 9.2 Baseline 暴露的问题

扩充数据后，baseline 指标如下：

| 指标 | Baseline |
|---|---:|
| Total cases | 30 |
| Positive cases | 27 |
| Negative cases | 3 |
| Hit@1 | 92.59% |
| Recall@5 | 100.00% |
| MRR | 0.9630 |
| Negative no-hit accuracy | 0.00% |
| Keyword coverage | 100.00% |
| Average latency | 141.726 ms |

主要问题：

| Case ID | Question | Expected | Baseline Top1 | 问题 |
|---|---|---|---|---|
| `activity_002` | 满减和优惠券能不能无限叠加？ | 商品活动规则 | 优惠券规则 | 只看“优惠券”导致活动规则被排到第 2 |
| `activity_003` | 秒杀订单超时未支付会怎样？ | 商品活动规则 | 支付规则 | “支付”泛化命中压过“秒杀/超时” |
| `negative_001` | 门店自提需要带身份证吗？ | 无命中 | 售后维修规则 | 低置信度也返回 |
| `negative_002` | 礼品卡余额能提现吗？ | 无命中 | 会员权益 | 低置信度也返回 |
| `negative_003` | 海外购商品清关需要多久？ | 无命中 | 退款规则 | 低置信度也返回 |

### 9.3 本次优化策略

本次只做轻量检索修复，没有引入外部依赖：

1. 增加最低向量分数阈值，过滤过低的 FAISS 命中。
2. 增加停用泛词，过滤 `规则`、`什么`、`怎么`、`需要`、`商品`、`订单` 等容易造成误召回的词。
3. 中文词法匹配优先使用 `jieba` 分词；当 `jieba` 不可用或没有切出有效词时，回退到 2-4 字 n-gram。
4. 增加候选文档内的 IDF 风格权重，让更稀有、更有区分度的词权重更高。
5. 要求弱向量命中至少覆盖 2 个有效查询词，避免只因一个词相同就返回结果。

说明：本次代码已将 `jieba` 加入 `backend/requirements.txt`，并已在当前本地 `.venv` 安装 `jieba==0.42.1`。命令行复测实际走的是 `jieba` 优先路径；单元测试同时覆盖了 `jieba` 可用路径和 2-4 字 n-gram 兜底路径。

### 9.4 优化后实际数据

| 指标 | Baseline | Optimized |
|---|---:|---:|
| Total cases | 30 | 30 |
| Positive cases | 27 | 27 |
| Negative cases | 3 | 3 |
| Hit@1 | 92.59% | 100.00% |
| Recall@5 | 100.00% | 100.00% |
| MRR | 0.9630 | 1.0000 |
| Negative no-hit accuracy | 0.00% | 100.00% |
| Keyword coverage | 100.00% | 100.00% |
| Average latency | 141.726 ms | 153.191 ms |

负样本复测结果：

| Case ID | Question | Optimized Result |
|---|---|---|
| `negative_001` | 门店自提需要带身份证吗？ | 无命中，正确 |
| `negative_002` | 礼品卡余额能提现吗？ | 无命中，正确 |
| `negative_003` | 海外购商品清关需要多久？ | 无命中，正确 |

### 9.5 当前结论

本轮优化提升了两个关键点：

- 活动类问题不再被支付/优惠券文档抢占 Top1。
- 知识库没有覆盖的问题可以返回无命中，不再强行把低相关文档塞给生成模型。

但当前评估仍然是 MVP 级别：

- 数据集只有 30 条，覆盖面还不够。
- 当前 embedding 仍可能使用本地 hash 兜底，不代表生产 embedding 效果。
- 还没有做 answer groundedness，也没有验证最终回答是否忠于检索片段。

下一步应该进入回答质量评估，而不是继续堆检索技巧。

## 10. 2026-05-06：回答质量评估 baseline

### 10.1 本次怎么测

评估目标：

- 验证当前 RAG 链路从“召回正确文档”进一步走到“回答可追溯、关键点覆盖、负例不胡答”。
- 先不依赖外部 LLM，而是使用确定性的抽取式回答 baseline，避免 API 可用性、温度、模型版本变化导致指标不可复现。
- 对正样本检查是否返回来源、来源是否为预期文档、回答是否覆盖关键关键词、是否包含禁止话术。
- 对负样本检查是否无命中并返回兜底回答。

评估数据：

- 数据集：`data/eval/answer_questions.json`
- 样本数：`12`
- 正样本：`10` 条，覆盖退款、发票、物流、会员、活动、维修、投诉、支付、优惠券、隐私账号。
- 负样本：`2` 条，分别是门店自提身份证、礼品卡余额提现，期望知识库无命中。
- 当前知识库：`data/raw` 下 10 份客服规则文档，重建后 FAISS metadata 文档数为 `10`。

本次实现文件：

| 文件 | 作用 |
|---|---|
| `data/eval/answer_questions.json` | 固定回答质量评估集 |
| `backend/scripts/evaluate_answer.py` | 回答评估脚本，统计来源返回、来源命中、关键词覆盖、禁用话术、可依据率和负例拒答 |
| `data/reports/answer_eval_report.json` | 本次实际评估输出 |

运行命令：

```powershell
cd backend
.venv\Scripts\python.exe scripts\build_kb.py --input ..\data\raw --report ..\data\reports\kb_build_report.md --database-url sqlite:///../data/reports/retrieval_eval.sqlite --init-db
.venv\Scripts\python.exe scripts\evaluate_answer.py --dataset ..\data\eval\answer_questions.json --report ..\data\reports\answer_eval_report.json --top-k 3 --source metadata
```

说明：

- `--source metadata` 表示脚本从当前 `data/vector_store/metadata.json` 创建临时 SQLite 评估库，再调用真实 `retrieve_documents()`。
- 回答生成方式是 `rag_extractive`：直接基于 top source 内容组装回答，因此本次主要验证 RAG 来源可追溯和保守回答能力。
- 这不是最终 LLM 生成质量评估；后续需要新增真实 `rag_llm` 模式，验证 Prompt 后的自然语言回答是否仍然忠于来源。

### 10.2 本次实际数据

| 指标 | 结果 |
|---|---:|
| Total cases | 12 |
| Positive cases | 10 |
| Negative cases | 2 |
| Top K | 3 |
| Source return rate | 100.00% |
| Source match rate | 100.00% |
| Keyword coverage | 100.00% |
| Forbidden violation rate | 0.00% |
| Groundedness rate | 100.00% |
| Negative no-hit accuracy | 100.00% |
| Average latency | 173.061 ms |

逐条结果：

| Case ID | Question | Expected Source | Top Source | Keyword Coverage | 判定 |
|---|---|---|---|---:|---|
| `answer_refund_001` | 商品已经拆封还能直接退款吗？ | 退款规则 | 退款规则 | 100.00% | 通过 |
| `answer_invoice_001` | 发票抬头写错了怎么办？ | 发票规则 | 发票规则 | 100.00% | 通过 |
| `answer_logistics_001` | 物流超过 72 小时没有更新怎么办？ | 物流规则 | 物流规则 | 100.00% | 通过 |
| `answer_member_001` | 金卡会员有哪些权益？ | 会员权益 | 会员权益 | 100.00% | 通过 |
| `answer_activity_001` | 秒杀订单超时未支付会怎样？ | 商品活动规则 | 商品活动规则 | 100.00% | 通过 |
| `answer_repair_001` | 人为损坏可以免费维修吗？ | 售后维修规则 | 售后维修规则 | 100.00% | 通过 |
| `answer_complaint_001` | 金额争议投诉需要提供什么凭证？ | 投诉处理规则 | 投诉处理规则 | 100.00% | 通过 |
| `answer_payment_001` | 重复扣款一般多久到账？ | 支付规则 | 支付规则 | 100.00% | 通过 |
| `answer_coupon_001` | 优惠券过期后可以恢复吗？ | 优惠券规则 | 优惠券规则 | 100.00% | 通过 |
| `answer_privacy_001` | 修改绑定手机号需要验证什么？ | 隐私与账号规则 | 隐私与账号规则 | 100.00% | 通过 |
| `answer_negative_001` | 门店自提需要带身份证吗？ | 无命中 | 无命中 | N/A | 正确兜底 |
| `answer_negative_002` | 礼品卡余额能提现吗？ | 无命中 | 无命中 | N/A | 正确兜底 |

### 10.3 当前结论

本轮 answer 评估说明当前链路已经具备最基础的回答安全边界：

- 正样本能返回来源，且来源文档全部命中预期。
- 回答内容来自知识库片段，没有出现测试集中列出的禁止话术。
- 知识库未覆盖的问题可以给出“未命中/转人工确认”的兜底，而不是编造答案。

但也要注意，这个结果是抽取式 baseline，难度低于真实 LLM 生成：

- 当前回答基本是引用知识原文，不代表最终用户体验已经自然。
- 关键词覆盖 100.00% 主要说明来源文档完整，不代表模型改写后仍能保留关键点。
- Groundedness 当前是规则代理指标，只能判断回答是否明显来自来源，不能替代人工质检或 LLM-as-judge。

### 10.4 下一步优化方向

1. 新增 `--mode chat` 或 `--mode llm`，调用真实 `run_chat_flow_with_context()`，评估最终 `rag_llm` 回复。
2. 将回答评估集扩到 30-50 条，加入追问、反问、模糊问法和跨文档问题。
3. 增加人工标注字段，例如 `expected_answer_points`，区分“关键词出现”和“语义真的答对”。
4. 增加低分阈值检查：当 top source 分数低于阈值时，强制输出未命中兜底。
5. 下一模块进入工具调用评估，覆盖订单查询、物流查询和投诉登记的路由与参数提取。

## 11. 2026-05-06：本地 Qwen RAG 回答评估

### 11.1 本次怎么测

评估目标：

- 在上一轮抽取式 answer baseline 的基础上，真实调用本地 Ollama Qwen，验证最终 `rag_llm` 回答质量。
- 继续使用同一批 `data/eval/answer_questions.json`，确保能和抽取式 baseline 对比。
- 正样本检查来源返回、来源命中、关键词覆盖、禁用话术和规则代理 groundedness。
- 负样本仍然先走检索无命中兜底，不让 LLM 对知识库外问题自由发挥。

本次实现变化：

| 文件 | 作用 |
|---|---|
| `backend/scripts/evaluate_answer.py` | 新增 `--mode extractive/llm`，`llm` 模式会调用 `run_chat_flow_with_context()` |
| `backend/tests/test_kb.py` | 新增 `llm` 模式单测，用测试桩验证真实 RAG 回复评分逻辑 |
| `data/reports/answer_eval_qwen.json` | 本次 Qwen 实际评估输出 |

运行命令：

```powershell
cd backend
.venv\Scripts\python.exe scripts\build_kb.py --input ..\data\raw --report ..\data\reports\kb_build_report.md --database-url sqlite:///../data/reports/retrieval_eval.sqlite --init-db
.venv\Scripts\python.exe scripts\evaluate_answer.py --dataset ..\data\eval\answer_questions.json --report ..\data\reports\answer_eval_qwen.json --top-k 3 --source metadata --mode llm
```

模型配置：

```env
LLM_API_BASE=http://127.0.0.1:11434/v1
LLM_API_KEY=ollama
LLM_MODEL_NAME=qwen3:8B
LLM_STRIP_THINKING=true
```

### 11.2 本次实际数据

| 指标 | Extractive Baseline | Qwen rag_llm |
|---|---:|---:|
| Total cases | 12 | 12 |
| Positive cases | 10 | 10 |
| Negative cases | 2 | 2 |
| Source return rate | 100.00% | 100.00% |
| Source match rate | 100.00% | 100.00% |
| Keyword coverage | 100.00% | 88.33% |
| Forbidden violation rate | 0.00% | 0.00% |
| Groundedness rate | 100.00% | 25.00% |
| Negative no-hit accuracy | 100.00% | 100.00% |
| Average latency | 173.061 ms | 3646.640 ms |
| Average retrieval latency | N/A | 183.693 ms |
| Average generation latency | N/A | 3462.934 ms |

LLM 模式延迟拆分：

| 范围 | Retrieval | Generation | Total |
|---|---:|---:|---:|
| 全部 12 条 | 183.693 ms | 3462.934 ms | 3646.640 ms |
| 正样本 10 条 | 189.113 ms | 4155.520 ms | 约 4344.633 ms |
| 负样本 2 条 | 156.591 ms | 0.003 ms | 156.606 ms |

逐条结果：

| Case ID | Question | Top Source | Keyword Coverage | Grounded | 观察 |
|---|---|---|---:|---|---|
| `answer_refund_001` | 商品已经拆封还能直接退款吗？ | 退款规则 | 66.67% | false | 回答可用，但仍有部分精确关键词被改写 |
| `answer_invoice_001` | 发票抬头写错了怎么办？ | 发票规则 | 100.00% | false | 答案正确，但补了“拨打热线”这类来源外表达 |
| `answer_logistics_001` | 物流超过 72 小时没有更新怎么办？ | 物流规则 | 75.00% | false | 漏掉精确短语 `没有更新`，语义基本正确 |
| `answer_member_001` | 金卡会员有哪些权益？ | 会员权益 | 100.00% | true | 回答简洁且覆盖关键点 |
| `answer_activity_001` | 秒杀订单超时未支付会怎样？ | 商品活动规则 | 66.67% | false | 漏掉 `限定时间`，但结论正确 |
| `answer_repair_001` | 人为损坏可以免费维修吗？ | 售后维修规则 | 100.00% | false | 结论正确，groundedness 规则对改写偏严 |
| `answer_complaint_001` | 金额争议投诉需要提供什么凭证？ | 投诉处理规则 | 100.00% | false | 结论正确，groundedness 规则对改写偏严 |
| `answer_payment_001` | 重复扣款一般多久到账？ | 支付规则 | 75.00% | false | 将 `自动退回` 改写成 `自动处理`，语义接近但规则扣分 |
| `answer_coupon_001` | 优惠券过期后可以恢复吗？ | 优惠券规则 | 100.00% | false | 结论正确，补了提醒语 |
| `answer_privacy_001` | 修改绑定手机号需要验证什么？ | 隐私与账号规则 | 100.00% | false | 答案过短但关键点正确 |
| `answer_negative_001` | 门店自提需要带身份证吗？ | 无命中 | N/A | true | 正确兜底 |
| `answer_negative_002` | 礼品卡余额能提现吗？ | 无命中 | N/A | true | 正确兜底 |

### 11.3 当前结论

本轮验证说明当前 RAG + 本地 Qwen 链路已经可以真实工作：

- 检索来源稳定，正样本 `Source match rate = 100.00%`。
- Qwen 没有触发禁止话术，`Forbidden violation rate = 0.00%`。
- 知识库外问题没有交给模型自由发挥，负样本 `Negative no-hit accuracy = 100.00%`。
- 平均耗时约 `3.65s`，其中平均检索约 `184ms`，平均生成约 `3.46s`。
- 正样本实际调用 Qwen，平均生成耗时约 `4.16s`；负样本无命中时不调用 Qwen，平均总耗时约 `157ms`。

同时也暴露了真实生成评估的问题：

- 关键词覆盖从 `100.00%` 降到 `85.00%`，说明模型会自然改写或省略部分关键表达。
- 当前 groundedness 规则更适合抽取式回答，对自然语言改写过严，因此 `25.00%` 不能直接理解为 75% 回答不可信。
- 个别回答会补充来源外建议，例如“拨打人工服务热线”“请尽快在规定时间内完成支付操作”，后续 Prompt 需要进一步约束。
- 延迟瓶颈主要来自本地 Qwen 生成，不是 RAG 检索。当前检索耗时仍处在百毫秒级，工具链路则是毫秒级。

### 11.4 下一步优化方向

1. 在 `answer_questions.json` 增加 `expected_answer_points`，把“语义点覆盖”和“精确关键词覆盖”分开评估。
2. 改进 groundedness：从原文片段硬匹配升级为句子级来源支持判断，或引入 LLM-as-judge 做二次评审。
3. 收紧 RAG Prompt：要求“不新增知识库未提及的联系方式、操作入口、承诺性建议”。
4. 对低覆盖样例做 Prompt 回归测试，重点是退款、活动、支付三类。
5. 下一模块进入工具调用评估，建立订单/物流/投诉的路由、工具选择和参数提取评估集。
6. 针对实时客服体验增加流式输出、回答长度上限和更小模型对比，目标是首 token 小于 1 秒、完整回答尽量控制在 2-4 秒。

## 12. 2026-05-06：订单/物流工具调用评估

### 12.1 本次怎么测

评估目标：

- 验证用户问题从 `chat_service` 进入后，是否能被正确路由到订单或物流工具。
- 不绕过聊天主链路，评估真实路径：`ChatRequest -> route_user_intent() -> ToolService -> 具体工具 -> tool_logs -> ChatResponseData`。
- 同时检查工具调用状态、关键槽位、回复关键片段和工具日志是否符合预期。

评估数据：

- 数据集：`data/eval/tool_cases.json`
- 样本数：`11`
- 订单工具：`5` 条，覆盖成功、按 user_id 单订单命中、多订单需补充订单号、订单不存在、缺少 user_id/订单号。
- 物流工具：`5` 条，覆盖按运单号命中、按订单号命中、多物流需补充订单号或运单号、物流不存在、缺少 user_id/单号。
- 路由优先级：`1` 条，覆盖“订单 + 物流”同时出现时优先走物流查询。

本次实现文件：

| 文件 | 作用 |
|---|---|
| `data/eval/tool_cases.json` | 固定工具调用评估集 |
| `backend/scripts/evaluate_tools.py` | 工具评估脚本，统计路由、工具选择、状态、槽位、回复关键片段和端到端准确率 |
| `data/reports/tool_eval_report.json` | 本次工具调用评估输出 |

运行命令：

```powershell
cd backend
.venv\Scripts\python.exe scripts\evaluate_tools.py --dataset ..\data\eval\tool_cases.json --report ..\data\reports\tool_eval_report.json --source ephemeral
```

说明：

- `--source ephemeral` 使用临时 SQLite 评估库，不依赖 MySQL/Redis，也不会污染本地业务库。
- 评估脚本会真实调用 `handle_chat_request()`，并从 `tool_logs` 中读取工具名、状态和结构化输出。

### 12.2 本次实际数据

| 指标 | 结果 |
|---|---:|
| Total cases | 11 |
| Route accuracy | 100.00% |
| Tool selection accuracy | 100.00% |
| Status accuracy | 100.00% |
| Answer source accuracy | 100.00% |
| Slot accuracy | 100.00% |
| Reply contains accuracy | 100.00% |
| End-to-end accuracy | 100.00% |
| Average latency | 2.459 ms |

逐条结果：

| Case ID | Message | Expected Tool | Status | 判定 |
|---|---|---|---|---|
| `tool_order_001` | 帮我查一下订单 ORD2026043001 的状态 | order_query | success | 通过 |
| `tool_order_002` | 查一下我的订单状态 | order_query | success | 通过 |
| `tool_order_003` | 帮我查一下订单状态 | order_query | needs_input | 通过 |
| `tool_order_004` | 帮我查一下订单 ORD9999999999 | order_query | not_found | 通过 |
| `tool_order_005` | 查订单 | order_query | needs_input | 通过 |
| `tool_logistics_001` | 帮我查一下物流 SF2026043001 到哪了 | logistics_query | success | 通过 |
| `tool_logistics_002` | 查询订单 ORD2026043002 的物流 | logistics_query | success | 通过 |
| `tool_logistics_003` | 帮我查一下物流状态 | logistics_query | needs_input | 通过 |
| `tool_logistics_004` | 帮我查物流 TRACK999999 | logistics_query | not_found | 通过 |
| `tool_logistics_005` | 查物流 | logistics_query | needs_input | 通过 |
| `tool_route_priority_001` | 帮我查一下订单 ORD2026043001 的物流进度 | logistics_query | success | 通过 |

### 12.3 当前结论

当前订单/物流工具链路已经具备可验证的业务办理能力：

- 高频订单查询和物流查询都能稳定路由到正确工具。
- 成功、缺参数、多结果、未找到四类状态都有明确输出。
- 工具调用会写入 `tool_logs`，评估脚本可以复查 tool name、status、input、output。
- 在“订单 + 物流”同时出现时，当前规则优先走 `logistics_query`，符合本轮预期。

当前边界：

- 评估集只覆盖订单和物流，投诉/工单工具尚未接入。
- 路由仍是关键词规则，复杂表达或错别字还没有覆盖。
- 参数提取依赖正则，只支持当前 mock 订单号和运单号格式。
- 平均耗时来自本地 mock 工具，不代表真实外部接口延迟。

### 12.4 下一步优化方向

1. 接入投诉/工单工具后扩充 `tool_cases.json`，增加 `complaint_create` 场景。
2. 为工具评估增加失败注入模式，统计工具异常时的 fallback 正确率。
3. 强化意图路由，增加“查快递”“包裹到哪了”“售后单进度”等非显式关键词表达。
4. 将工具调用日志与 trace 串联到评估报告，方便面试或复盘时展示可观测链路。
5. 后续可把 `evaluate_retrieval.py`、`evaluate_answer.py`、`evaluate_tools.py` 汇总成统一 `evaluate_all.py`。

## 13. 后续报告模板

每次改动检索或 Agent 策略后，在这里新增一条记录。

### YYYY-MM-DD：实验名称

变更内容：

- TODO

运行命令：

```powershell
cd backend
.venv\Scripts\python.exe scripts\evaluate_retrieval.py --dataset ..\data\eval\retrieval_questions.json --top-k 5
```

结果汇总：

| 策略 | 样本数 | Hit@1 | Recall@3 | Recall@5 | MRR | 平均耗时 |
|---|---:|---:|---:|---:|---:|---:|
| baseline_vector | TODO | TODO | TODO | TODO | TODO | TODO |
| hybrid_bm25_vector | TODO | TODO | TODO | TODO | TODO | TODO |

错误样本：

| Case ID | Question | Gold Doc | Top1 Doc | 问题类型 | 后续处理 |
|---|---|---|---|---|---|
| TODO | TODO | TODO | TODO | TODO | TODO |

结论：

- TODO
