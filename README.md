# ServiceMind - 智能客服 Agent 系统

## 1. 项目核心定位

ServiceMind 是一个面向电商、零售与本地生活场景的智能客服 Agent 系统，目标是通过 `大模型 + RAG 知识库 + 业务工具调用` 的组合能力，完成用户咨询应答、订单与物流查询、投诉受理、售后引导等客服任务，降低人工客服成本并提升服务响应效率。

项目强调三类能力的一体化落地：

- `智能问答`：对商品、规则、售后政策、活动说明等知识进行自然语言问答。
- `业务办理`：通过工具调用完成订单查询、物流跟踪、工单创建、投诉登记等动作。
- `多轮协同`：支持上下文记忆、意图识别、场景切换和复杂问题分步处理。

> 说明：当前仓库尚未包含完整源码实现，本文档基于项目目标、图示信息与典型落地方案整理，可直接作为该项目的实现说明、立项文档与开发参考基线。

## 2. 技术栈详情

### 2.1 前端

- 前端框架：`Vue 3 + TypeScript`
- 构建工具：`Vite`
- 路由管理：`Vue Router`
- 状态管理：`Pinia`
- 网络请求：`Axios`
- 图标组件：`lucide-vue-next`
- 实时输出：当前为普通 HTTP 联调，后续演进为 `SSE / WebSocket`

### 2.2 后端

- 后端语言：`Python 3.11+`
- Web 框架：`FastAPI`
- Agent 编排：`LangChain`
- 模型接入：`DeepSeek API`，兼容 OpenAI 风格接口
- 模型微调框架：`PyTorch + Transformers + PEFT + LoRA`
- 任务调度：`Celery`（可选）+ `Redis`
- 部署方式：`Docker + Docker Compose`

### 2.3 数据层与中间件

- 关系型数据库：`MySQL 8.0`
- 缓存与会话态：`Redis`
- 向量检索：当前使用本地 `FAISS` 索引，后续可按规模评估 `ChromaDB`
- 关键词检索：当前保留轻量词法检索作为 FAISS 失败回退，后续演进为 `BM25`
- 对象存储：本地文件系统或 `MinIO`
- 日志监控：`Loguru + Prometheus + Grafana`

### 2.4 AI 与工具层

- RAG 检索：当前为 `文本分块 + Embedding + FAISS 向量召回 + 词法回退 + 来源返回`
- Embedding 模型：优先使用 OpenAI-compatible `/embeddings`，未配置时使用本地哈希 embedding 兜底；后续可切换 `bge-small-zh / bge-base-zh`
- Agent 模式：`ReAct / Tool Calling`
- 工具协议：`MCP（Model Context Protocol）`
- 客服业务工具：
  - 订单信息查询
  - 物流轨迹查询
  - 用户历史投诉记录查询
  - 工单创建/升级
  - 优惠券补偿/人工转接

## 3. 项目核心内容

### 3.1 业务场景

- 售前咨询：商品介绍、规格差异、活动规则、推荐问答
- 售中服务：订单状态、支付异常、配送时效、物流跟踪
- 售后处理：退换货政策、退款进度、投诉登记、人工升级

### 3.2 核心能力

- 多轮对话与上下文记忆
- 客服场景意图识别与问题路由
- 基于 RAG 的企业知识问答
- 基于 MCP/Tool Calling 的业务系统对接
- FAQ 类问题自动回复
- 复杂问题自动拆解与多步骤处理
- 会话日志、工具调用日志、检索日志可追踪

### 3.3 系统目标

- 将高频重复咨询自动化处理
- 提高客服响应速度和答案一致性
- 降低人工客服压力
- 支持从 MVP 到生产系统的渐进式演进

## 4. 当前项目结构与职责

```text
ServiceMind/
├─ README.md
├─ docs/
│  ├─ architecture.md
│  ├─ development-guide.md
│  └─ mvp-plan.md
├─ backend/
│  ├─ app/
│  │  ├─ agents/
│  │  ├─ api/
│  │  ├─ core/
│  │  ├─ db/
│  │  ├─ middleware/
│  │  ├─ models/
│  │  ├─ rag/
│  │  ├─ repositories/
│  │  ├─ schemas/
│  │  ├─ services/
│  │  ├─ tools/
│  │  ├─ utils/
│  │  └─ main.py
│  ├─ scripts/
│  ├─ tests/
│  ├─ .env.example
│  └─ requirements.txt
├─ frontend/
│  ├─ src/
│  │  ├─ assets/
│  │  ├─ router/
│  │  ├─ services/
│  │  ├─ stores/
│  │  ├─ types/
│  │  └─ views/
│  ├─ package.json
│  ├─ vite.config.ts
│  └─ tsconfig.json
```

### 4.1 后端分层职责

- `app/main.py`
  - FastAPI 应用入口，负责创建应用、挂载路由、注册中间件和生命周期事件。
- `app/api/`
  - HTTP 接口层，只做请求接收、参数校验、调用 service、返回统一响应。
- `app/schemas/`
  - Pydantic 请求/响应模型，约束接口输入输出格式。
- `app/services/`
  - 业务编排层，处理具体业务流程，不直接暴露给外部。
- `app/repositories/`
  - 数据访问层，负责数据库读写，避免在 service 中直接写 SQL。
- `app/models/`
  - SQLAlchemy ORM 模型，定义表结构和关系。
- `app/db/`
  - 数据库连接、Redis 连接、BaseModel 等基础设施。
- `app/agents/`
  - Agent 编排逻辑，包括意图识别、记忆管理、Prompt 模板、执行路由。
- `app/rag/`
  - 知识库摄取、切分、向量化、检索、重排等能力。
- `app/tools/`
  - 订单、物流、投诉等可调用业务工具，后续可演化为 MCP 工具。
- `app/core/`
  - 配置、日志、安全、异常等跨模块基础能力。
- `app/middleware/`
  - 请求链路上下文、异常处理中间件等横切逻辑。
- `app/utils/`
  - 时间、ID、常量等通用辅助工具。
- `scripts/`
  - 构建知识库、导入数据、初始化系统等离线脚本。
- `tests/`
  - 接口测试、服务测试、集成测试。

### 4.2 前端分层职责

- `src/views/`
  - 页面级工作台，目前提供用户侧聊天联调界面。
- `src/stores/`
  - Pinia 状态层，管理会话 ID、消息列表、健康检查状态、发送状态和错误信息。
- `src/services/`
  - Axios 请求封装，对接 `/api/v1/health` 与 `/api/v1/chat/`。
- `src/router/`
  - Vue Router 入口，当前挂载单页工作台，后续可扩展管理端页面。
- `src/types/`
  - 前后端联调用到的统一响应、健康检查、聊天请求和聊天响应类型。

## 5. 开发环境要求

### 5.1 基础环境

- `Node.js >= 18`
- `pnpm >= 8` 或 `npm >= 9`
- `Python >= 3.11`
- `MySQL >= 8.0`
- `Redis >= 7`
- `Git`
- `Docker` 与 `Docker Compose`（推荐）

### 5.2 模型与 API 配置

需要准备以下环境变量：

- `LLM_API_BASE`
- `LLM_API_KEY`
- `LLM_MODEL_NAME`
- `EMBEDDING_MODEL_NAME`
- `DATABASE_URL` 或 `MYSQL_HOST/MYSQL_PORT/MYSQL_USER/MYSQL_PASSWORD/MYSQL_DATABASE`
- `MYSQL_HOST`
- `MYSQL_PORT`
- `MYSQL_USER`
- `MYSQL_PASSWORD`
- `MYSQL_DATABASE`
- `REDIS_HOST`
- `REDIS_PORT`

示例 `.env`：

```env
# 方式一：直接使用完整数据库连接串
DATABASE_URL=mysql+pymysql://root:your_password@localhost:3306/servicemind

# 方式二：使用拆分变量（未提供 DATABASE_URL 时生效）
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=123456
MYSQL_DATABASE=servicemind

# DeepSeek API（OpenAI 兼容）
LLM_API_BASE=https://api.deepseek.com
LLM_API_KEY=your_api_key
LLM_MODEL_NAME=deepseek-chat
EMBEDDING_MODEL_NAME=BAAI/bge-small-zh-v1.5

REDIS_HOST=127.0.0.1
REDIS_PORT=6379
```

如果你使用本地 Ollama（例如 `qwen3`），可改为：

```env
LLM_API_BASE=http://127.0.0.1:11434/v1
LLM_API_KEY=ollama
LLM_MODEL_NAME=qwen3
EMBEDDING_MODEL_NAME=BAAI/bge-small-zh-v1.5
```

## 6. 快速启动步骤

### 6.1 使用 Docker Compose 启动基础依赖

```bash
docker compose up -d mysql redis
```

### 6.2 启动后端服务

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Windows PowerShell：

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 6.3 启动前端开发服务

```powershell
cd frontend
npm install
npm run dev
```

前端开发服务默认运行在 `http://127.0.0.1:5173/console/`，Vite 会把 `/api` 代理到 `http://127.0.0.1:8000`。

### 6.4 构建前端并由后端托管

```powershell
cd frontend
npm run build
cd ../backend
.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

构建产物输出到 `frontend/dist/`。后端启动时若检测到该目录，会把前端工作台挂载到 `http://127.0.0.1:8000/console/`。

### 6.5 当前阶段说明

- 当前仓库已完成 `backend` 基础链路与 `frontend` Vue 工程初始化。
- 前端已具备健康检查、聊天发送、会话 ID 展示、trace 展示、订单/物流/退款示例入口。
- 当前前后端联调覆盖 `/api/v1/health`、`/api/v1/chat/`、知识库上传/分块/FAISS 向量索引/检索来源、订单工具、物流工具和工具日志。
- 流式输出、复杂管理后台、人工接管 UI 仍属于后续增强范围。

### 6.6 初始化知识库

```bash
cd backend
python scripts/build_kb.py --input ../data/raw --report ../data/reports/kb_build_report.md --init-db
```

脚本会批量读取 `data/raw` 下的 `.txt` 和 `.md` 文件，清洗、切分、写入知识库并重建 `data/vector_store` 下的 FAISS 索引，同时输出处理报告。

### 6.7 使用本地 Ollama Qwen 验证 RAG 回答

`.env` 中配置本地 Qwen：

```env
LLM_API_BASE=http://127.0.0.1:11434/v1
LLM_API_KEY=ollama
LLM_MODEL_NAME=qwen3:8b
LLM_TIMEOUT_SECONDS=120
LLM_STRIP_THINKING=true
```

命令行验证：

```powershell
cd backend
.venv\Scripts\python.exe scripts\run_rag_chat.py "商品已经拆封还能直接退款吗？" --top-k 3 --source metadata
```

正常情况下会输出 `Answer source: rag_llm`、命中的知识库来源和 Qwen 生成的最终回答。

评估本地 Qwen 的真实 RAG 回答质量：

```powershell
cd backend
.venv\Scripts\python.exe scripts\evaluate_answer.py --dataset ..\data\eval\answer_questions.json --report ..\data\reports\answer_eval_qwen.json --top-k 3 --source metadata --mode llm
```

评估订单/物流工具调用链路：

```powershell
cd backend
.venv\Scripts\python.exe scripts\evaluate_tools.py --dataset ..\data\eval\tool_cases.json --report ..\data\reports\tool_eval_report.json --source ephemeral
```

### 6.8 可用性验证

- 打开前端工作台页面
- 发起一个商品、订单或物流类问题
- 检查系统是否完成：
  - 意图识别
  - FAISS 向量召回或词法回退
  - 知识来源展示
  - 工具调用
  - 答案生成
  - 日志落库

本地验证命令：

```powershell
cd frontend
npm run build

cd ../backend
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe scripts\run_smoke.py --base-url http://127.0.0.1:8000
```

## 7. 项目文档导航

- 架构拆分与流程图：[architecture.md](/D:/pythoncode/ServiceMind/docs/architecture.md)
- 开发手册与实现说明：[development-guide.md](/D:/pythoncode/ServiceMind/docs/development-guide.md)
- MVP 方案与优先级：[mvp-plan.md](/D:/pythoncode/ServiceMind/docs/mvp-plan.md)
- 阶段验证与评估结果：[evaluation-report.md](/D:/pythoncode/ServiceMind/docs/evaluation-report.md)

## 8. 推荐开发顺序

1. 完成 `health`、配置加载、统一响应体、异常处理中间件，确保服务可稳定启动。
2. 打通 `chat` 主接口的空链路，先返回固定响应，跑通请求流程。
3. 补 `session`、`message` 表结构与持久化逻辑，先实现会话保存与查询。
4. 实现知识库导入、切分、向量化和基础检索，完成最小 RAG 闭环。
5. 接入订单查询与物流查询两个高频工具，形成 `Agent + RAG + Tool` 主链路。
6. 补离线数据处理 pipeline，支持批量清洗、分块、embedding、索引重建和处理报告。
7. 补阶段验证链路，用固定问题集统计 Hit@1、Recall@K、MRR、回答可依据率和工具调用正确率。
8. 最后补投诉、工单、监控看板、自动评测平台和微调能力。

## 9. 版本演进建议

### MVP 阶段

- 支持 FAQ 问答
- 支持订单/物流查询
- 支持投诉登记
- 支持简单多轮对话

### V1 阶段

- 加入混合检索与重排序
- 增强场景意图识别
- 增加会话质检与监控面板
- 支持人工接管与工单流转

### V2 阶段

- 引入 LoRA 微调后的领域模型
- 支持多租户与权限控制
- 接入更多业务系统
- 建立自动评测与 A/B 实验机制

## 10. 项目价值

- 适合作为 AI Agent + RAG + MCP 工具调用的综合实践项目
- 适合作为校招或社招简历中的完整落地案例
- 适合作为电商客服、企业知识问答、智能工单助手的原型基础
