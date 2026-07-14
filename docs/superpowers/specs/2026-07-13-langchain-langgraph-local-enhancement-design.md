# LangChain + LangGraph 本地单人增强版设计

日期：2026-07-13  
状态：待用户最终审核

## 1. 背景

现有项目是一个 FastAPI + 原生 JavaScript 的知识问答原型，使用阿里云百炼模型、Pinecone 向量库和 Redis。它已经具备聊天、团队知识录入、个人记忆录入和混合检索雏形，但存在以下核心问题：

- 问答流程由同步服务方法串联，缺少可观察、可恢复的工作流状态。
- 个人记忆绑定 `session_id`，不能自然跨会话复用。
- Redis 中的 BM25 语料采用整块 JSON 读写，扩展性和一致性较差。
- Pinecone 是事实存储与搜索索引的混合体，无法自然支持列表、编辑、删除和状态管理。
- API 只返回是否使用 RAG，不返回可验证的文档引用。
- 外部客户端在模块导入阶段初始化，一个依赖失败可能阻止服务启动。
- 前端以录入为主，缺少会话、文档、记忆和索引任务的完整管理能力。
- 缺少项目级自动化测试、结构化日志和错误降级策略。

## 2. 目标

将项目重构为本地单人使用的 AI 知识工作台：

- 使用 LangGraph 编排可控、有限重试的问答流程。
- 使用 LangChain 统一模型、Embedding、Document、Splitter 和 Retriever 接口。
- 使用 SQLite 保存会话、消息、文档、片段、个人记忆和任务状态。
- 继续使用 Pinecone 作为语义向量索引，并保留现有数据。
- 移除 Redis 运行依赖。
- 提供 SQLite FTS5 + Pinecone 的混合检索。
- 每个回答返回可点击、可核对的来源引用。
- 提供知识库、个人记忆、记忆建议和会话的完整管理页面。
- 默认测试不访问真实百炼或 Pinecone 服务。

## 3. 非目标

本轮不实现：

- 多用户登录、JWT、SSO、角色和团队权限。
- 多租户数据隔离。
- 完全离线的本地模型和本地向量库。
- 分布式任务队列和多实例部署。
- 扫描 PDF 的 OCR；接口保留扩展点，但首版仅支持可提取文本的 PDF。
- 自由决策、无限工具调用的 Agent。

## 4. 总体架构

系统分为以下层次：

### 4.1 API 层

FastAPI 负责：

- 请求与响应校验。
- SSE 流式响应。
- 统一错误响应。
- 健康检查与运行诊断。
- 静态前端资源服务。

API 层不得直接调用 Pinecone SDK 或执行 SQL。

### 4.2 Application 层

应用用例负责：

- 创建、查询、重命名和删除会话。
- 文档与个人记忆入库。
- 文档编辑、删除、重新索引。
- 记忆建议确认、编辑和拒绝。
- 旧数据迁移。
- SQLite 与 Pinecone 一致性检查。

### 4.3 Domain 层

领域模型包括：

- Conversation
- Message
- Document
- Chunk
- Memory
- MemoryCandidate
- Citation
- IngestionJob
- MigrationRecord

领域对象不依赖 FastAPI、SQLAlchemy、Pinecone 或具体模型供应商。

### 4.4 Infrastructure 层

基础设施适配器包括：

- SQLite Repository。
- Pinecone VectorStore。
- 阿里云百炼 Chat Model 与 Embedding Model。
- PDF/Text Document Loader。
- LangGraph SQLite Checkpointer。
- 结构化日志和可选 LangSmith tracing。

### 4.5 Workflows 层

LangGraph 工作流负责聊天状态和节点流转。节点只依赖协议接口，测试时使用 Fake Model、Fake Retriever 和临时 SQLite。

## 5. 项目目录设计

```text
backend/app/
  api/
    chat.py
    conversations.py
    documents.py
    memories.py
    diagnostics.py
  application/
    chat_use_case.py
    document_use_case.py
    memory_use_case.py
    migration_use_case.py
  domain/
    entities.py
    errors.py
    ports.py
  infrastructure/
    db/
      models.py
      repositories.py
      session.py
      migrations.py
    llm/
      dashscope.py
    vectorstores/
      pinecone.py
    retrieval/
      fts.py
      hybrid.py
    documents/
      loaders.py
      splitters.py
  workflows/
    chat_graph.py
    state.py
    nodes.py
  config.py
  dependencies.py
  main.py
backend/tests/
  unit/
  integration/
  api/
  e2e/
scripts/
  migrate_pinecone_to_sqlite.py
  check_index_consistency.py
```

## 6. SQLite 数据模型

### 6.1 conversations

- `id`: UUID，主键，同时作为 LangGraph `thread_id`。
- `title`: 会话标题。
- `created_at`, `updated_at`。
- `status`: active / archived。

### 6.2 messages

- `id`: UUID。
- `conversation_id`: 外键。
- `role`: user / assistant / system。
- `content`: 消息正文。
- `status`: pending / completed / failed。
- `error_code`, `error_message`: 失败时填写。
- `citations_json`: 助手消息的引用快照，默认为空列表。
- `warnings_json`: 检索降级等非致命警告，默认为空列表。
- `created_at`。

### 6.3 documents

- `id`: UUID。
- `title`, `category`。
- `source_type`: text / pdf。
- `source_name`: 文件名或文本标题。
- `content_hash`: 去重与变更检测。
- `status`: pending / indexing / indexed / failed / deleting。
- `error_message`。
- `created_at`, `updated_at`。

### 6.4 chunks

- `id`: UUID。
- `document_id`: 可空，知识文档片段时填写。
- `memory_id`: 可空，个人记忆片段时填写。
- `content`: 完整片段正文。
- `page_number`: PDF 页码，可空。
- `chunk_index`。
- `token_count`。
- `vector_id`: Pinecone ID，唯一。
- `namespace`: rag / ltm。
- `created_at`。

SQLite FTS5 虚拟表索引 chunk 正文、标题和分类，并通过触发器或 Repository 同步维护。

### 6.5 memories

- `id`: UUID。
- `title`, `content`。
- `kind`: preference / fact / decision / context。
- `source_type`: manual / conversation / migrated。
- `source_conversation_id`: 可空。
- `status`: confirmed / archived。
- `created_at`, `updated_at`。

个人记忆属于唯一的本地用户空间，不再按会话过滤。

### 6.6 memory_candidates

- `id`: UUID。
- `conversation_id`, `message_id`。
- `proposed_title`, `proposed_content`, `kind`。
- `status`: pending / confirmed / rejected。
- `created_at`, `reviewed_at`。

候选记忆只有确认后才创建 Memory 和向量。

### 6.7 ingestion_jobs

- `id`: UUID。
- `resource_type`, `resource_id`。
- `status`: pending / running / completed / failed。
- `attempt_count`。
- `error_code`, `error_message`。
- `created_at`, `updated_at`。

首版本地模式可在 FastAPI 进程内执行入库任务，但任务状态必须持久化，失败后可手动重试。

### 6.8 migration_records

- `id`: UUID。
- `namespace`, `vector_id`: 联合唯一。
- `target_type`, `target_id`。
- `migrated_at`。

用于保证迁移脚本幂等。

## 7. LangGraph 聊天状态

Graph State 包含：

```text
messages
conversation_id
standalone_query
knowledge_docs
memory_docs
ranked_docs
citations
retry_count
answer
memory_candidates
warnings
```

LangGraph 使用 SQLite checkpointer，以 `conversation_id` 作为 `thread_id`。SQLite 中的 messages 表用于产品级查询和展示；checkpointer 用于恢复 Graph 状态。两者职责分离，不直接读取 checkpointer 内部表构建前端历史。

## 8. LangGraph 问答流程

### 8.1 receive_query

- 校验问题长度。
- 创建 pending 用户消息。
- 从 checkpointer 恢复 thread state。

### 8.2 understand_query

- 根据近期消息生成独立问题和检索查询。
- 简单、上下文无关的问题允许跳过模型改写。

### 8.3 retrieve_context

知识库与已确认个人记忆并行检索：

- SQLite FTS5 各取 Top 20。
- Pinecone 语义检索各取 Top 20。
- 知识库使用 `rag` namespace。
- 个人记忆使用 `ltm` namespace。

### 8.4 merge_and_rank

- 使用 chunk ID 去重。
- 使用 Reciprocal Rank Fusion 合并关键词和向量排名。
- 应用最低相关性规则。
- 知识和记忆分别设最大数量，避免个人记忆挤占知识来源。
- 最终最多选择 6 个片段。

### 8.5 evaluate_context

判断资料是否足以回答：

- 足够：进入答案生成。
- 不足且 `retry_count == 0`：改写查询并再检索一次。
- 不足且已重试：进入明确无资料的回答路径。

Graph 不允许无限循环。

### 8.6 generate_answer

- 文档片段放入清晰分隔的“不可信参考资料”区域。
- 系统提示明确禁止执行资料中的指令。
- 每个片段分配稳定 citation ID。
- 通过 SSE 逐步返回 token。

### 8.7 validate_citations

- 引用必须对应实际选中的 chunk。
- 删除不存在的引用编号。
- 没有相关资料时不生成伪引用。
- 引用包含标题、分类、片段 ID、PDF 页码和简短摘录。

### 8.8 persist_result

- 将助手消息标记 completed。
- 保存 citations。
- 更新会话标题和时间。
- Graph 失败时将用户消息保留，并记录 failed 状态和可重试错误。

### 8.9 propose_memories

- 在回答完成后识别 preference、fact、decision、context 类型信息。
- 与现有记忆去重。
- 仅写入 memory_candidates。
- 用户确认后才写入 memories 与 Pinecone。

## 9. 文档和记忆入库

### 9.1 校验

- 文本不得为空。
- PDF 必须通过扩展名、MIME 和文件头检查。
- 默认最大文件 20 MB。
- 默认最大 300 页。
- 提取后文本总量设置上限，超过时给出明确错误。

### 9.2 加载与分块

- 使用 LangChain Document 表示文本。
- PDF 每页保留 `page_number` 和 `source` 元数据。
- 使用 token-aware splitter，不再按固定字符数粗切。
- 默认目标约 500 tokens，重叠约 80 tokens，配置可覆盖。

### 9.3 一致性状态机

```text
pending -> indexing -> indexed
                    -> failed
indexed -> deleting -> deleted
```

入库步骤：

1. SQLite 创建 document/memory 和 chunks，状态 pending。
2. 进入 indexing。
3. 批量生成 Embedding。
4. 批量写入 Pinecone。
5. 成功后写入 vector_id 并标记 indexed。
6. 失败时保留原始记录和错误，允许重试。

删除时先标记 deleting，再删除 Pinecone 向量和 SQLite 数据。任何一步失败都保留可恢复状态。

## 10. 混合检索

新检索替换 Redis BM25：

- SQLite FTS5 提供中文/英文关键词检索。首版使用 Unicode tokenizer；中文检索质量通过测试语料校验，必要时在 Repository 层增加 jieba 预分词列。
- Pinecone 提供语义向量检索。
- HybridRetriever 通过 LangChain Retriever 接口暴露。
- RRF 参数、候选数量和最终 Top-K 进入配置。
- 返回 Document 对象，metadata 至少包含 chunk_id、resource_id、resource_type、title、category、page_number 和 vector_id。

## 11. 旧数据迁移

迁移目标是保留 Pinecone 中现有 `rag` 和 `ltm` 向量，不重新 Embedding。

### 11.1 rag namespace

- 枚举 vector ID 并 fetch metadata。
- 按 title、category 和 source_type 聚合为 documents。
- 每个向量补建 chunk，沿用原 vector_id。
- 缺少页码的数据保留 page_number 为空。

### 11.2 ltm namespace

- 每个现有向量导入为 confirmed memory 或 memory chunk。
- `session_id` 仅作为迁移来源信息保留，不再参与新检索过滤。
- title 缺失时使用“迁移记忆”。

### 11.3 幂等性和安全

- namespace + vector_id 唯一。
- 支持 `--dry-run` 输出将创建的记录数量。
- 正式迁移前备份 SQLite 文件。
- 重复运行不会重复创建。
- 迁移不删除或修改 Pinecone 现有向量。

## 12. API 设计

保留兼容入口，并新增管理接口。

### 12.1 聊天

- `POST /api/chat/session`：创建会话，保留兼容。
- `POST /api/chat`：非流式兼容入口，内部调用同一 Graph。
- `POST /api/chat/stream`：SSE 流式聊天。
- `GET /api/conversations`：会话列表。
- `GET /api/conversations/{id}/messages`：消息和引用。
- `PATCH /api/conversations/{id}`：重命名或归档。
- `DELETE /api/conversations/{id}`：删除会话状态和消息。

### 12.2 知识库

- `GET /api/documents`：分页、搜索、分类和状态过滤。
- `POST /api/documents/text`。
- `POST /api/documents/pdf`。
- `GET /api/documents/{id}`：文档和片段详情。
- `PATCH /api/documents/{id}`：修改标题、分类或文本内容。
- `POST /api/documents/{id}/reindex`。
- `DELETE /api/documents/{id}`。

旧 `/api/knowledge/text` 和 `/api/knowledge/pdf` 保留为兼容别名。

### 12.3 个人记忆

- `GET /api/memories`。
- `POST /api/memories`。
- `PATCH /api/memories/{id}`。
- `DELETE /api/memories/{id}`。
- `GET /api/memory-candidates`。
- `POST /api/memory-candidates/{id}/confirm`。
- `POST /api/memory-candidates/{id}/reject`。

旧 `/api/memory/text` 和 `/api/memory/pdf` 保留为兼容入口，但不再要求 session_id 作为数据隔离条件。

### 12.4 诊断

- `GET /api/health/live`：仅检查进程。
- `GET /api/health/ready`：检查 SQLite、Pinecone 和配置。
- `GET /api/diagnostics`：返回各组件状态、索引统计和一致性摘要，不返回密钥。

## 13. 前端设计

前端保持无需 Node 构建的 HTML/CSS/JavaScript，降低本地运行成本，但重写为模块化 JavaScript。

### 13.1 对话页

- 左侧显示会话列表和新建会话按钮。
- 刷新页面从 API 恢复会话和消息。
- SSE 显示检索、重排、生成、校验阶段。
- 答案下显示可点击引用。
- 引用详情展示标题、分类、页码和原文片段。
- 失败消息可点击重试。

### 13.2 知识库页

- 文档表格、搜索、分类和状态过滤。
- 上传文本/PDF。
- 显示 pending、indexing、indexed、failed、deleting。
- 查看片段、错误、重新索引和删除。

### 13.3 个人记忆页

- 已确认记忆列表。
- 待确认建议列表和数量提示。
- 支持确认前编辑、拒绝、修改和删除。

### 13.4 运行状态页

- SQLite 状态。
- Pinecone 索引、维度和 namespace 统计。
- Chat Model 与 Embedding 配置状态。
- SQLite/Pinecone 一致性摘要。
- 迁移状态和手动重试入口。

## 14. 错误处理和降级

- Pinecone 不可用时，知识检索降级为 SQLite FTS5，并在回答中返回 warning。
- 模型不可用时，保存用户消息并返回可重试错误。
- Embedding 或 Pinecone 写入失败时，资源保持 failed 状态。
- PDF 解析失败不创建已索引资源。
- 外部调用均设置连接、读取和总超时。
- 查询改写检索最多重试一次。
- API 返回稳定错误结构：`code`、`message`、`request_id`、可选 `details`。
- 未知异常记录完整服务端 traceback，前端只显示安全错误信息。

## 15. 安全

- CORS 默认只允许 `http://127.0.0.1:*` 和 `http://localhost:*` 的开发配置；同源部署时可关闭 CORS。
- 上传限制格式、大小、页数和文本量。
- 文档内容作为不可信资料处理，不能覆盖系统指令。
- 日志不输出 API Key、完整 Prompt、Embedding 或整篇文档。
- `.env.example` 只包含占位符。
- 当前已暴露的百炼与 Pinecone Key 必须轮换。
- 外部客户端延迟初始化，`/api/health/live` 不依赖外部服务。

## 16. 可观测性

结构化日志字段至少包括：

- request_id
- conversation_id / thread_id
- graph_node
- duration_ms
- retrieval_candidate_count
- selected_document_count
- citation_count
- error_code

LangSmith tracing 通过环境变量可选开启，不作为本地运行和测试的必要依赖。

## 17. 测试设计

### 17.1 单元测试

- Token-aware 分块和元数据保留。
- RRF 排序、去重和 Top-K。
- 引用构建和无效引用过滤。
- 文档状态机。
- 记忆建议确认与去重。
- 配置校验和错误映射。

### 17.2 LangGraph 测试

- 资料充分路径。
- 第一次不足、改写后成功路径。
- 两次不足后的明确无资料路径。
- Pinecone 失败时 FTS 降级路径。
- 模型失败的消息状态。
- 记忆候选仅待确认、不自动写入。

Graph 测试使用确定性 Fake，不访问真实模型。

### 17.3 集成测试

- 临时 SQLite Repository CRUD。
- FTS 索引同步。
- 文档入库状态转换。
- Pinecone 适配器使用 Fake/Mock contract。
- 迁移 dry-run、正式迁移和重复运行幂等。
- FastAPI API 和 SSE 事件顺序。

### 17.4 浏览器测试

- 创建、切换和恢复会话。
- 流式回答与引用展开。
- 文档上传、状态、查看、重建和删除。
- 记忆建议编辑、确认和拒绝。
- 桌面和移动端关键视口无内容重叠。

### 17.5 测试约束

- 默认测试禁止真实网络调用。
- 真实百炼/Pinecone 测试标记为 `live`，仅手动运行。
- 核心 domain、application、workflow 代码覆盖率目标不低于 80%。

## 18. 依赖变化

新增的主要依赖预计包括：

- langchain
- langgraph
- langchain-openai
- langchain-pinecone
- langgraph-checkpoint-sqlite
- sqlalchemy
- aiosqlite
- tiktoken 或模型兼容 tokenizer
- pytest
- pytest-asyncio
- pytest-cov
- respx

移除运行依赖：

- redis
- rank-bm25

`jieba` 是否保留由 SQLite FTS5 中文检索基准决定；首版实现允许作为可选预分词器。

## 19. 实施阶段

### 阶段 1：基础骨架和测试设施

- 新目录结构。
- 配置、依赖注入、SQLite、Repository。
- 单元测试和 Fake adapters。

### 阶段 2：文档、记忆和迁移

- Loader、Splitter、入库状态机。
- Pinecone 与 FTS HybridRetriever。
- 旧数据迁移与一致性检查。

### 阶段 3：LangGraph 聊天

- State、节点、条件边。
- Checkpointer、SSE、引用和记忆建议。
- 兼容旧聊天 API。

### 阶段 4：管理工作台

- 会话、知识、记忆、诊断页面。
- 删除、重建、错误重试。

### 阶段 5：验收和清理

- 全量自动化测试。
- 浏览器截图和响应式检查。
- 移除旧 Redis/BM25 代码与依赖。
- 更新启动脚本和研发文档。

## 20. 验收标准

- 无 Redis 环境下可以启动并完成多轮聊天。
- 现有 Pinecone 中 4 个向量可迁移到 SQLite，重复迁移不增加记录。
- 会话刷新后仍可恢复。
- 个人记忆跨会话参与检索。
- 每个基于资料的回答包含可定位引用。
- Pinecone 不可用时关键词检索仍可工作并显示降级警告。
- 知识和记忆可查看、编辑、删除和重新索引。
- 记忆候选未经确认不会参与检索。
- 默认测试不发起真实网络请求。
- 核心模块覆盖率达到 80% 目标。
- 桌面与移动端关键流程无内容重叠。

## 21. 已确认决策

- 产品形态：本地单人增强版，免登录。
- 工作流：LangChain + LangGraph 可控流程。
- 存储：SQLite + Pinecone，移除 Redis 必需依赖。
- 迁移：保留并迁移现有 Pinecone 数据。
- 个人记忆：手动录入 + 自动建议，确认后保存。
- 实施方式：模块化重建，兼容现有主要 API。
