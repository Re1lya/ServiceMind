# ServiceMind 开发手册

## 1. 文档目标

本文档面向开发者，解决三个问题：

1. 这个项目准备做成什么样
2. 现在代码骨架各目录分别负责什么
3. 后续应该按什么顺序把能力一点点实现出来

如果你第一次接手这个项目，建议按以下顺序阅读：

1. [README.md](/D:/pythoncode/ServiceMind/README.md)
2. [architecture.md](/D:/pythoncode/ServiceMind/docs/architecture.md)
3. 本文档
4. [mvp-plan.md](/D:/pythoncode/ServiceMind/docs/mvp-plan.md)

## 2. 当前开发状态

当前仓库已经完成：

- 项目级说明文档
- 架构与 MVP 文档
- 后端 Python 工程骨架
- FastAPI 应用入口
- API 分层目录
- Agent / RAG / Tools / Services / Repositories 等模块占位
- Vue 3 前端工程骨架
- 前端健康检查与聊天工作台联调页面

当前仓库尚未完成：

- 生产级数据库与 Redis 部署配置
- 流式输出与前端增量渲染
- 更完整的 Agent 编排策略
- 更完整的 RAG 向量化与重排序能力
- 投诉登记、人工接管和管理端页面

也就是说，现在这个项目已经从“纯骨架”进入“可联调的 MVP 主链路”阶段，前端可以验证健康检查、聊天请求、订单/物流工具路由和后端兜底能力。

## 3. 后端目录详细说明

```text
backend/
├─ app/
│  ├─ main.py
│  ├─ api/
│  ├─ core/
│  ├─ db/
│  ├─ middleware/
│  ├─ models/
│  ├─ schemas/
│  ├─ repositories/
│  ├─ services/
│  ├─ agents/
│  ├─ rag/
│  ├─ tools/
│  └─ utils/
├─ scripts/
├─ tests/
├─ .env.example
└─ requirements.txt
```

## 4. 前端目录详细说明

```text
frontend/
├─ src/
│  ├─ assets/
│  ├─ router/
│  ├─ services/
│  ├─ stores/
│  ├─ types/
│  ├─ views/
│  ├─ App.vue
│  └─ main.ts
├─ index.html
├─ package.json
├─ tsconfig.json
└─ vite.config.ts
```

前端当前采用 `Vue 3 + TypeScript + Vite`，并以 `Vue Router + Pinia + Axios` 组成基础生态。

- `src/views/WorkbenchView.vue`
  - 用户侧客服工作台，负责健康状态展示、示例问题入口、消息列表和输入区。
- `src/stores/chat.ts`
  - 管理会话 ID、消息列表、发送状态、健康检查结果和错误信息。
- `src/services/http.ts`
  - Axios 基础实例，默认请求 `/api/v1`。
- `src/services/chatApi.ts`
  - 封装 `GET /health` 与 `POST /chat/`。
- `src/types/api.ts`
  - 对齐后端统一响应体、健康检查响应和聊天响应结构。
- `vite.config.ts`
  - 开发期将 `/api` 代理到后端 `http://127.0.0.1:8000`；生产构建默认使用 `/console/` base，便于由 FastAPI 静态挂载。

### 3.1 `app/main.py`

作用：

- 创建 FastAPI 应用实例
- 挂载主路由
- 后续注册中间件、异常处理、生命周期事件

你后续会在这里继续补：

- CORS
- 全局异常处理
- 请求上下文中间件
- startup/shutdown 逻辑
- metrics/trace 注册

### 3.2 `app/api/`

作用：

- 管理 HTTP 接口
- 控制版本路由
- 接收请求并调用 service

开发规则：

- API 层不要直接写数据库逻辑
- API 层不要直接调用模型或向量库
- API 层只做“接收请求 -> 参数校验 -> 调 service -> 返回结果”

### 3.3 `app/schemas/`

作用：

- 定义所有请求和响应的 Pydantic 模型
- 保证输入输出格式稳定

建议约定：

- `xxxRequest` 表示请求体
- `xxxResponse` 表示响应体
- 公共响应结构单独放在 `common.py`

### 3.4 `app/services/`

作用：

- 组织业务逻辑
- 串联 repository、agent、rag、tools 等多个模块

典型关系：

- `chat_service` 调 `agent orchestrator`
- `kb_service` 调 `rag ingestion / vector store`
- `tool_service` 调 `tool registry`

开发规则：

- service 是“业务主入口”
- 复杂流程优先放 service，不要堆在 API 层

### 3.5 `app/repositories/`

作用：

- 处理数据库读写
- 对 service 层屏蔽 ORM 细节

推荐做法：

- 一个聚合对象一个 repository
- 尽量避免在多个 service 中重复写相同查询逻辑

### 3.6 `app/models/`

作用：

- 定义 MySQL 中的数据表结构

当前建议优先落地的表：

- `sessions`
- `messages`
- `knowledge_documents`
- `tool_logs`

第二阶段可补：

- `knowledge_chunks`
- `feedback_records`
- `complaint_tickets`
- `agent_traces`

### 3.7 `app/db/`

作用：

- 定义 SQLAlchemy Base
- 创建数据库 session
- 初始化 Redis 客户端

建议：

- `session.py` 专门放数据库 engine 和 sessionmaker
- `redis.py` 专门放 Redis 连接与封装

### 3.8 `app/agents/`

作用：

- 实现 Agent 主链路
- 管理 Prompt
- 管理会话记忆
- 根据意图决定走检索还是工具调用

后续建议职责拆分：

- `router.py`
  - 判断问题属于 FAQ、订单、物流、投诉还是复杂咨询
- `memory.py`
  - 维护短期上下文和摘要记忆
- `prompts.py`
  - 放系统提示词、场景提示词、工具提示词
- `orchestrator.py`
  - 统一串联路由、检索、工具与答案生成

### 3.9 `app/rag/`

作用：

- 负责知识库构建和检索

模块分工建议：

- `ingestion.py`
  - 文档读取、清洗、切分、元数据打标
- `embeddings.py`
  - 初始化 embedding 模型
- `vector_store.py`
  - 向量存储建索引、写入、删除、更新
- `retriever.py`
  - 召回逻辑
- `reranker.py`
  - 重排序逻辑

### 3.10 `app/tools/`

作用：

- 把外部业务能力封装成 Agent 可调用工具

建议规范：

- 每个工具单文件
- 每个工具定义：
  - 输入参数
  - 调用方法
  - 错误处理
  - 返回标准结构

### 3.11 `app/core/`

作用：

- 提供项目基础能力

建议职责：

- `config.py`
  - 环境变量与配置加载
- `logging.py`
  - 日志初始化
- `security.py`
  - 鉴权、签名、权限控制
- `exceptions.py`
  - 业务异常定义

### 3.12 `app/middleware/`

作用：

- 处理横切逻辑

常见内容：

- trace_id 注入
- 全局异常捕获
- 请求耗时统计
- 用户上下文注入

### 3.13 `scripts/`

作用：

- 离线任务和运维脚本

建议后续补充：

- `build_kb.py`
- `import_seed_data.py`
- `reindex_kb.py`
- `backfill_sessions.py`
- `evaluate_retrieval.py`
- `evaluate_answer.py`
- `evaluate_tools.py`

离线数据处理脚本的最小目标是：从 `data/raw` 批量读取原始知识文档，完成文本清洗、语义分块、embedding 生成、FAISS 索引重建，并输出文档数、chunk 数、失败数和耗时。所有离线脚本都应保留可追踪日志，避免只在接口请求时临时处理数据。

### 3.14 `tests/`

作用：

- 放接口测试、服务测试、集成测试

建议最先补的测试：

- `health` 接口测试
- 配置加载测试
- chat 主链路 smoke test
- 检索模块基本测试

## 5. 请求处理链路

以“用户问：我的订单什么时候到？”为例，推荐请求链路如下：

1. 前端请求进入 `/api/v1/chat`
2. API 层解析 `session_id`、用户消息、上下文信息
3. `chat_service` 接收请求，写入当前消息
4. `agent.orchestrator` 判断问题类型
5. 如果识别为物流类问题，调用 `tool_service`
6. `tool_service` 从 `tool_registry` 找到 `logistics_query` 工具
7. 工具调用上游接口，返回物流结果
8. Agent 将结果组织成自然语言回复
9. 回复写入 `messages`
10. API 层返回结构化响应或流式响应

这条链路说明了一个核心原则：

- API 层不做业务判断
- Service 层不直接写 SQL
- Tool 层不负责拼最终用户文案
- Agent 层负责“理解与编排”

## 6. 推荐数据模型设计

以下是当前最值得优先落地的 4 张核心表。

### 5.1 `sessions`

用途：

- 表示一段对话会话

建议字段：

- `id`
  - 主键，自增或雪花 ID，用于数据库内部唯一标识。
- `session_id`
  - 会话业务 ID，前后端交互时使用，便于按会话查询整段聊天。
- `user_id`
  - 用户唯一标识，用于区分不同用户的会话。
- `channel`
  - 会话来源渠道，例如 web、app、wechat，用于统计和隔离接入来源。
- `status`
  - 会话状态，例如 active、closed、handoff，用于表示当前会话生命周期。
- `created_at`
  - 会话创建时间，用于排序和审计。
- `updated_at`
  - 最近更新时间，用于展示最近活跃会话和增量同步。

### 5.2 `messages`

用途：

- 保存每一轮对话消息

建议字段：

- `id`
  - 消息主键，用于唯一标识一条消息。
- `session_id`
  - 所属会话 ID，用于把多条消息归并到同一段对话。
- `role`
  - 消息角色，例如 user、assistant、system、tool，用于区分消息来源。
- `content`
  - 消息正文，保存用户问题、模型回复或工具摘要内容。
- `message_type`
  - 消息类型，例如 text、tool_result、summary，用于区分不同消息用途。
- `trace_id`
  - 链路追踪 ID，用于把本轮请求涉及的日志、检索、工具调用串起来。
- `created_at`
  - 消息创建时间，用于按时间顺序恢复对话。

### 5.3 `knowledge_documents`

用途：

- 记录知识库源文档信息

建议字段：

- `id`
  - 文档主键，用于唯一标识一份知识源文档。
- `title`
  - 文档标题，用于后台展示和检索结果来源标记。
- `source_path`
  - 文档原始存储路径，用于重新构建索引或问题回溯。
- `source_type`
  - 文档类型，例如 pdf、md、txt，用于选择不同解析策略。
- `status`
  - 文档处理状态，例如 uploaded、parsed、indexed、failed。
- `chunk_count`
  - 切分后的片段数量，用于评估文档规模和索引情况。
- `created_at`
  - 文档录入时间，用于追踪知识库版本。

### 5.4 `tool_logs`

用途：

- 记录业务工具调用情况

建议字段：

- `id`
  - 日志主键，用于唯一标识一次工具调用记录。
- `session_id`
  - 所属会话 ID，用于关联本次工具调用是由哪段对话触发的。
- `tool_name`
  - 工具名称，例如 order_query、logistics_query，用于统计工具使用情况。
- `request_payload`
  - 工具调用入参快照，用于排查调用时传了什么参数。
- `response_payload`
  - 工具返回结果快照，用于排查工具本身是否返回异常数据。
- `success`
  - 是否调用成功，用于统计工具可用率。
- `error_message`
  - 错误信息，用于记录调用失败原因。
- `created_at`
  - 工具调用时间，用于排查问题和生成时序日志。

## 6.5 表结构设计补充建议

为了减少后续返工，建表时建议同时注意这几点：

- `session_id`、`user_id`、`trace_id` 尽量加索引
  - 这些字段是最常见的查询条件。
- `request_payload`、`response_payload` 建议使用 `JSON`
  - 便于保留原始调用内容，也方便后期检索。
- `status`、`role`、`message_type` 建议用短字符串或枚举
  - 有利于统一约束与状态统计。
- 时间字段统一为 `datetime`
  - 便于排序、审计和运维排查。

## 7. 文件与函数级开发视角

如果你更习惯“看文件和函数来理解项目”，建议把后端功能按下面这套方式理解。

### 6.1 一个问答功能会经过哪些文件

用户问题进入后，推荐依次经过：

1. [backend/app/main.py](/D:/pythoncode/ServiceMind/backend/app/main.py)
   - `create_app()` 创建应用并挂载总路由
2. [backend/app/api/router.py](/D:/pythoncode/ServiceMind/backend/app/api/router.py)
   - `api_router` 负责挂载 API 路由
3. [backend/app/api/v1/router.py](/D:/pythoncode/ServiceMind/backend/app/api/v1/router.py)
   - `v1_router` 负责挂载 V1 版本接口
4. [backend/app/api/v1/endpoints/chat.py](/D:/pythoncode/ServiceMind/backend/app/api/v1/endpoints/chat.py)
   - `create_chat_completion()` 作为 HTTP 入口
5. [backend/app/services/chat_service.py](/D:/pythoncode/ServiceMind/backend/app/services/chat_service.py)
   - `handle_chat_request()` 作为聊天业务主入口
6. [backend/app/agents/orchestrator.py](/D:/pythoncode/ServiceMind/backend/app/agents/orchestrator.py)
   - `run_chat_flow()` 负责编排问答链路
7. [backend/app/agents/router.py](/D:/pythoncode/ServiceMind/backend/app/agents/router.py)
   - `route_user_intent()` 决定走检索还是工具调用
8. [backend/app/rag/](/D:/pythoncode/ServiceMind/backend/app/rag/) 或 [backend/app/tools/](/D:/pythoncode/ServiceMind/backend/app/tools/)
   - 根据路由结果进入检索逻辑或工具调用逻辑
9. [backend/app/repositories/message_repository.py](/D:/pythoncode/ServiceMind/backend/app/repositories/message_repository.py)
   - 保存用户消息与助手回复

### 6.2 一个检索功能会经过哪些文件

如果用户问题被判定为知识问答，推荐依次经过：

1. [backend/app/agents/router.py](/D:/pythoncode/ServiceMind/backend/app/agents/router.py)
   - `route_user_intent()`
2. [backend/app/rag/retriever.py](/D:/pythoncode/ServiceMind/backend/app/rag/retriever.py)
   - `retrieve_documents()`
   - `hybrid_search()`
3. [backend/app/rag/vector_store.py](/D:/pythoncode/ServiceMind/backend/app/rag/vector_store.py)
   - 负责向量库召回
4. [backend/app/rag/reranker.py](/D:/pythoncode/ServiceMind/backend/app/rag/reranker.py)
   - `rerank_documents()`
5. [backend/app/agents/orchestrator.py](/D:/pythoncode/ServiceMind/backend/app/agents/orchestrator.py)
   - `generate_answer()`

### 6.3 一个知识库构建功能会经过哪些文件

推荐依次经过：

1. [backend/app/api/v1/endpoints/kb.py](/D:/pythoncode/ServiceMind/backend/app/api/v1/endpoints/kb.py)
   - `upload_knowledge_document()`
   - `rebuild_knowledge_index()`
2. [backend/app/services/kb_service.py](/D:/pythoncode/ServiceMind/backend/app/services/kb_service.py)
   - `process_upload()`
   - `rebuild_index()`
3. [backend/app/rag/ingestion.py](/D:/pythoncode/ServiceMind/backend/app/rag/ingestion.py)
   - `load_documents()`
   - `split_documents()`
4. [backend/app/rag/embeddings.py](/D:/pythoncode/ServiceMind/backend/app/rag/embeddings.py)
   - `embed_documents()`
5. [backend/app/rag/vector_store.py](/D:/pythoncode/ServiceMind/backend/app/rag/vector_store.py)
   - `upsert_documents()`
6. [backend/app/repositories/kb_repository.py](/D:/pythoncode/ServiceMind/backend/app/repositories/kb_repository.py)
   - `save_document_metadata()`

### 6.4 一个工具调用功能会经过哪些文件

推荐依次经过：

1. [backend/app/agents/router.py](/D:/pythoncode/ServiceMind/backend/app/agents/router.py)
   - `route_user_intent()`
2. [backend/app/services/tool_service.py](/D:/pythoncode/ServiceMind/backend/app/services/tool_service.py)
   - `invoke_tool()`
3. [backend/app/tools/tool_registry.py](/D:/pythoncode/ServiceMind/backend/app/tools/tool_registry.py)
   - `get_tool()`
4. [backend/app/tools/order_query.py](/D:/pythoncode/ServiceMind/backend/app/tools/order_query.py)
   - `execute_order_query()`
5. [backend/app/tools/logistics_query.py](/D:/pythoncode/ServiceMind/backend/app/tools/logistics_query.py)
   - `execute_logistics_query()`
6. [backend/app/models/tool_log.py](/D:/pythoncode/ServiceMind/backend/app/models/tool_log.py)
   - 保存工具调用日志

### 6.5 关于“函数名为什么文档里有，但代码里还没有”

当前仓库还是开发骨架阶段，所以很多函数名是“推荐你后续按这个名字去实现”的约定函数，不是已经写好的现成函数。

这样做的好处是：

- 你现在就能看清未来每个能力会落在哪个文件
- 你实现时不容易把逻辑写散
- 文档、代码结构、功能流程能保持一致

如果后面你决定改函数名，建议同步改动本文档和 `architecture.md`，避免文档与实现脱节。

## 8. 接口设计建议

建议统一响应结构，避免后续前后端联调混乱。

### 7.1 成功响应

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

### 7.2 失败响应

```json
{
  "code": 10001,
  "message": "tool invocation failed",
  "data": null
}
```

### 7.3 Chat 接口建议

`POST /api/v1/chat`

请求体建议：

```json
{
  "session_id": "sess_xxx",
  "message": "我的订单什么时候到？",
  "stream": false,
  "user_id": "u_001"
}
```

响应体建议：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "session_id": "sess_xxx",
    "reply": "TODO",
    "route": "logistics_query",
    "answer_source": "tool",
    "trace_id": "trace_xxx",
    "user_message_id": "msg_xxx",
    "assistant_message_id": "msg_xxx",
    "knowledge_sources": []
  }
}
```

知识问答命中时，`knowledge_sources` 会返回本次注入回答上下文的知识片段：

```json
{
  "document_id": "doc_xxx",
  "title": "退款规则",
  "source_type": "text",
  "source_path": "data/raw/refund.md",
  "score": 6.0,
  "snippet": "平台支持七天无理由退款，商品需要保持完好。"
}
```

当前 RAG 是最小可用向量实现：上传和重建会先清洗文本，再按长度切成可检索片段，然后生成 embedding 并重建本地 FAISS 索引。检索时优先走 FAISS 向量召回；如果 FAISS 不可用、没有有效命中，或索引与当前数据库记录不同步，则回退到轻量词法评分。聊天链路把 top hits 注入 LLM prompt，并把来源返回给前端。后续若切换 Chroma/Milvus/Qdrant，应优先保持 `knowledge_sources` 响应结构稳定。

FAISS 相关文件：

- `data/vector_store/servicemind.faiss`
  - 本地向量索引文件。
- `data/vector_store/metadata.json`
  - 向量位置与知识片段元数据的映射。
- `backend/app/rag/embeddings.py`
  - 负责 OpenAI-compatible embedding 调用；未配置可用服务时使用本地哈希 embedding 兜底。
- `backend/app/rag/vector_store.py`
  - 负责 FAISS 索引重建、加载和相似度查询。

## 9. 开发优先级建议

### 当前前端联调命令

```powershell
cd frontend
npm install
npm run dev
```

开发服务默认访问 `http://127.0.0.1:5173/console/`，并通过 Vite proxy 将 `/api` 转发到后端 `http://127.0.0.1:8000`。

生产托管验证：

```powershell
cd frontend
npm run build
cd ../backend
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

构建后的工作台由后端挂载到 `http://127.0.0.1:8000/console/`。

### 第一阶段：把服务跑起来

- 完善 `config.py`
- 完善统一响应结构
- 完善异常处理中间件
- 保证 `/health` 可访问

目标：

- 服务能本地稳定启动
- 接口基本可调试

### 第二阶段：打通聊天空链路

- 定义 chat request/response schema
- 完善 `chat_service`
- 实现固定回复版本的 chat 接口
- 接入基础 session/message 保存

目标：

- 用户发消息后，系统能形成会话闭环

### 第三阶段：实现最小 RAG

- 完成知识文档导入
- 文本切分
- 基础来源追踪
- embedding 生成
- FAISS 本地向量召回
- 轻量词法回退
- 将检索结果拼入 prompt

目标：

- FAQ 类问题能根据知识库回答，并在前端展示来源片段

### 第四阶段：接入工具调用

- 先做订单查询
- 再做物流查询
- 最后做投诉登记

目标：

- FAQ 之外的业务问题也能处理

### 第五阶段：增强稳定性

- 日志和 trace
- 错误兜底
- 低置信度转人工
- 测试补齐

目标：

- 系统可演示、可排错、可迭代

### 第六阶段：补离线数据处理 pipeline

- 完善 `backend/scripts/build_kb.py`
- 支持从 `data/raw` 批量读取 TXT/Markdown，后续扩展 PDF/DOCX
- 在 `backend/app/rag/ingestion.py` 统一清洗、切分和元数据打标
- 调用 `backend/app/rag/embeddings.py` 生成 embedding
- 调用 `backend/app/rag/vector_store.py` 重建 FAISS 索引
- 记录每个文档的处理状态、chunk 数、失败原因和处理耗时
- 输出一次构建报告，后续同步写入 [evaluation-report.md](/D:/pythoncode/ServiceMind/docs/evaluation-report.md)

目标：

- 知识库构建从“接口即时处理”升级为“可重复运行的离线处理链路”
- 后续面试或复盘时能说明原始数据如何变成 Agent/RAG 可用数据

本地运行命令：

```powershell
cd backend
.venv\Scripts\python.exe scripts\build_kb.py --input ..\data\raw --report ..\data\reports\kb_build_report.md --init-db
```

### 第七阶段：补阶段效果验证

- 新建 `data/eval/retrieval_questions.json`，沉淀固定检索问题集
- 新建 `backend/scripts/evaluate_retrieval.py`，统计 Hit@1、Recall@3、Recall@5、MRR
- 新建 `data/eval/answer_questions.json`，验证回答是否引用来源、是否覆盖关键点、是否出现无依据内容
- 新建 `data/eval/tool_cases.json`，验证订单、物流、投诉等工具选择是否正确
- 每次调整 RAG、Prompt、Agent 路由后，都把结果写入 [evaluation-report.md](/D:/pythoncode/ServiceMind/docs/evaluation-report.md)

目标：

- 不再只说“加了 HyDE、BM25、Rerank”，而是能说明每个策略对召回和回答质量有没有提升
- 形成 Baseline -> 优化策略 -> 指标对比 -> 错误样本复盘的闭环

### 第八阶段：接入本地 Ollama Qwen 做 RAG 增强回答

当前后端 LLM 客户端兼容 OpenAI 风格接口，因此本地 Ollama 可以通过 `/v1/chat/completions` 直接接入。

推荐 `.env` 配置：

```env
LLM_API_BASE=http://127.0.0.1:11434/v1
LLM_API_KEY=ollama
LLM_MODEL_NAME=qwen3:8b
LLM_TIMEOUT_SECONDS=120
LLM_STRIP_THINKING=true
```

当前 RAG 回答链路：

1. `chat_service.handle_chat_request()` 根据用户问题调用 `retrieve_documents()`。
2. 检索结果被转换为 `knowledge_context`。
3. `orchestrator.run_chat_flow_with_context()` 将知识库来源注入 RAG system prompt。
4. 本地 Qwen 生成回答。
5. `extract_chat_text()` 会清理 Qwen3 可能输出的 `<think>...</think>` 思考块。
6. 接口返回 `answer_source=rag_llm` 和 `knowledge_sources`，前端可展示来源片段。

不启动前端时，可以直接用脚本验证本地 RAG 问答：

```powershell
cd backend
.venv\Scripts\python.exe scripts\build_kb.py --input ..\data\raw --report ..\data\reports\kb_build_report.md --database-url sqlite:///../data/reports/retrieval_eval.sqlite --init-db
.venv\Scripts\python.exe scripts\run_rag_chat.py "商品已经拆封还能直接退款吗？" --top-k 3 --source metadata
```

如果输出 `Answer source: rag_llm`，说明已经完成“检索增强 + 本地模型回答”闭环。如果输出 `fallback`，优先检查 Ollama 是否启动、模型名是否与 `ollama list` 一致、`LLM_API_BASE` 是否带 `/v1`。

接入 Qwen 后，可以用真实 LLM 模式复跑回答质量评估：

```powershell
cd backend
.venv\Scripts\python.exe scripts\evaluate_answer.py --dataset ..\data\eval\answer_questions.json --report ..\data\reports\answer_eval_qwen.json --top-k 3 --source metadata --mode llm
```

`--mode extractive` 用来测检索来源本身是否完整，`--mode llm` 用来测最终模型回答是否仍然覆盖关键点、忠于来源并正确兜底。

`evaluate_answer.py` 会在报告中输出 `retrieval_latency_ms`、`generation_latency_ms` 和 `latency_ms`：

- `retrieval_latency_ms`：检索召回耗时。
- `generation_latency_ms`：回答生成耗时；在 `--mode llm` 下基本就是本地 Qwen 调用耗时。
- `latency_ms`：本轮评估总耗时。

如果总耗时过高，优先看 `generation_latency_ms` 是否明显大于检索耗时。当前本地 Qwen 开发环境中，RAG 检索通常是百毫秒级，真实模型生成是秒级。

### 第九阶段：工具调用评估

工具评估用于验证订单、物流等业务办理链路是否稳定，覆盖 route、tool、status、slot 和回复片段。

固定测试集位于：

```text
data/eval/tool_cases.json
```

运行命令：

```powershell
cd backend
.venv\Scripts\python.exe scripts\evaluate_tools.py --dataset ..\data\eval\tool_cases.json --report ..\data\reports\tool_eval_report.json --source ephemeral
```

`--source ephemeral` 会创建临时 SQLite 评估库，适合本地快速验证；如果要评估真实业务库和历史日志，可以改用 `--source database`。

## 10. 推荐编码约束

- API 层不写业务逻辑
- Service 层不直接操作 request 对象
- Repository 层不拼装业务文案
- Tool 层返回结构化数据，不直接承担最终回复语气
- Prompt 放在 `agents/prompts.py`，不要散落在各处
- 所有异常尽量转换成统一业务异常
- 所有关键链路保留 `trace_id`

## 11. 常见开发坑

### 10.1 把业务逻辑全堆进接口层

问题：

- 后期难测试、难复用、难维护

正确做法：

- 接口层轻、service 层重

### 10.2 让 LLM 直接决定业务字段

问题：

- 容易幻觉，尤其订单和物流状态不可信

正确做法：

- 业务字段必须来自工具返回或数据库结果

### 10.3 知识库文档切分过粗

问题：

- 检索命中率低，回答引用不准

正确做法：

- 分块尽量语义完整，保留标题、段落和来源信息

### 10.4 不保留调用日志

问题：

- 出问题后无法排查是模型错、工具错还是检索错

正确做法：

- 保留请求、检索、工具、回复四类日志

## 12. 你接下来最应该做什么

如果你想按最稳的方式推进，建议直接照这个顺序开发：

1. 完善 [backend/app/core/config.py](/D:/pythoncode/ServiceMind/backend/app/core/config.py)
2. 完善 [backend/app/schemas/common.py](/D:/pythoncode/ServiceMind/backend/app/schemas/common.py)
3. 完善 [backend/app/middleware/error_handler.py](/D:/pythoncode/ServiceMind/backend/app/middleware/error_handler.py)
4. 完善 [backend/app/db/session.py](/D:/pythoncode/ServiceMind/backend/app/db/session.py)
5. 完善 [backend/app/models/session.py](/D:/pythoncode/ServiceMind/backend/app/models/session.py)
6. 完善 [backend/app/models/message.py](/D:/pythoncode/ServiceMind/backend/app/models/message.py)
7. 完善 [backend/app/services/chat_service.py](/D:/pythoncode/ServiceMind/backend/app/services/chat_service.py)
8. 完善 [backend/app/api/v1/endpoints/chat.py](/D:/pythoncode/ServiceMind/backend/app/api/v1/endpoints/chat.py)
9. 完善 [backend/app/rag/ingestion.py](/D:/pythoncode/ServiceMind/backend/app/rag/ingestion.py)
10. 完善 [backend/app/rag/retriever.py](/D:/pythoncode/ServiceMind/backend/app/rag/retriever.py)
11. 完善 [backend/app/tools/order_query.py](/D:/pythoncode/ServiceMind/backend/app/tools/order_query.py)
12. 完善 [backend/app/tools/logistics_query.py](/D:/pythoncode/ServiceMind/backend/app/tools/logistics_query.py)
13. 完善 [backend/scripts/build_kb.py](/D:/pythoncode/ServiceMind/backend/scripts/build_kb.py)，形成离线索引构建入口
14. 新增 `backend/scripts/evaluate_retrieval.py`，形成固定检索评估入口
15. 维护 [docs/evaluation-report.md](/D:/pythoncode/ServiceMind/docs/evaluation-report.md)，持续记录阶段验证结果和召回数据

## 13. 文档维护建议

后续每实现一个模块，建议同步更新三类信息：

- 模块职责是否变化
- 接口字段是否变化
- 表结构或流程是否变化

建议保持：

- README 讲全局
- architecture 讲架构
- development-guide 讲开发落地
- mvp-plan 讲范围和优先级
