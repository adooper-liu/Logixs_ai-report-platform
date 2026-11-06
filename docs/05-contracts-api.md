# 05 · 数据对象、契约与 API

## 1. 元数据库（设计，不是迁移文件）

所有业务对象使用 UUID，带 project_id、created/updated、revision；时间统一存 UTC，来源业务时间另存语义。配置 JSON 必须按版本化 schema 校验，不把所有关系塞入无类型 JSON。

| 对象 | 关键字段/约束 |
| --- | --- |
| Project / Membership / RoleGrant | 用户、角色、项目、作用域；对象读写每次校验 |
| Connection | adapter、host/endpoint、secret_ref、network policy；不存明文凭据 |
| Source / Stream | 稳定来源/逻辑数据流、connection、locator spec、技术 schema 引用；业务说明可空 |
| SchemaVersion / Column | 原始名、位置、stable column_id、类型、格式、fingerprint；列改名需显式映射 |
| RawObject | object URI/version、checksum、size、retention/classification；content identity 与批次分开 |
| IngestionBatch / BatchPart | source/stream、extract ID、coverage、cutoff、manifest、状态、完整性；多 part |
| Checkpoint | 接入读取与消费处理各自进度、revision、source token，提交时 CAS |
| Profile / Evidence | schema/batch、样本范围、本地统计、evidence IDs、访问分类 |
| RuleSetVersion | input schema、规则 AST、policy、compiler digest、不可改写版本 |
| ModelVersion / Relation | 输入契约、粒度、键、join、incremental、tests、权限 |
| MetricVersion / SemanticTerm | 公式 AST、维度、分母、时间、单位、scope；术语不是执行规则 |
| PipelineVersion / InputRole | DAG、required/optional、cutoff/freshness/completeness、规则/模型版本 |
| RunGroup / Run / Attempt | 固定输入、执行计划、stage、lease/fencing、outputs、错误、idempotency key |
| QualityResult / Issue | rule、scope、数量、错误码、样本引用、action；原始错误值隔离保护 |
| AIRequest / Recommendation / Application | intent、scope、input fingerprints、模型/usage、schema、候选、验证、采用记录 |
| Release / DatasetOutput | 主题、输入和输出清单、规则/模型/指标、warehouse transaction identity |
| AuditEvent / Outbox | actor、动作、对象版本、correlation ID；outbox 可幂等投递 |

warehouse 中维护 release manifest 和 active pointer 的权威副本；control Release 是可恢复投影。Superset DB 独立，不能把其内部模型当平台元数据权威源。

## 2. 配置契约类别

- connector spec：来源定位、字段、只读策略、分页/快照、checkpoint。
- schema contract：列 ID、原始类型、规范类型、nullable、格式、敏感等级、来源。
- rule contract：白名单 operator+明确参数+输出类型+失败动作。
- model contract：输入、grain、key、relations、attributes、tests。
- metric contract：表达式、可加性、时间、分母、null/除零和单位。
- pipeline contract：输入依赖、就绪策略、DAG、资源、提交模式、质量策略。
- publication contract：输出数据集、release coherence、schema compatibility、回退保留。
- AI recommendation contract：候选、证据、假设、歧义、验证要求，不是可任意执行的代码。

schema_version 表示文件结构版本；version 表示业务配置版本；两者不可混用。已被 Run 使用的版本不可原地编辑。更改产生新版本，当前指针独立更新并做 CAS。

## 3. 接口设计

HTTP `/api/v1`，JSON；异步动作返回 202+run/task ID，处理状态用分页轮询或 SSE。异步失败状态不伪装 HTTP 成功结果；错误结构：code、message、object_ref、stage、retryable、trace_id，不回传密钥/SQL 连接字符串。

| API 草案 | 行为 |
| --- | --- |
| POST /projects/{id}/connections:test | 最小只读连通性检查，限制网络范围 |
| POST /sources /streams | 建立稳定接入对象；可由批量上传流程自动生成草稿 |
| POST /uploads:init /uploads:complete | 获得受限上传目标、提交 checksum 和 finalized manifest |
| POST /batches | 多对象/多 sheet/抽取 parts，指定 stream、范围和完整性 |
| POST /profiles | 异步本地剖析，返回统计与证据引用 |
| POST /ai/recommendations | 授权上下文生成建议，记录成本和外发策略 |
| POST /recommendations/{id}:trial | 契约校验、编译、资源受限试运行 |
| POST /recommendations/{id}:apply | CAS 检查输入/规则仍适用，保存版本；不是审核 |
| POST /rulesets /models /metrics | 保存草案/版本，规则与模型测试为独立异步动作 |
| POST /pipelines/{id}:run | 固定 pipeline/input versions，支持业务范围和 dry-run |
| GET /runs/{id} /issues | 状态、阶段、计数、质量、分页错误和血缘 |
| POST /runs/{id}:retry /:cancel | 创建 attempt 或协作取消；不可改写发布结果 |
| POST /releases/{id}:publish /:rollback | 发布权限+自动检查+expected pointer，仓库事务 |
| POST /query-plans | NL/结构化语义查询，权限编译和固定 release |
| POST /query-plans/{id}:execute | 只读角色、配额、超时，结果来源与版本 |
| POST /reports:draft | 基于授权数据集创建 BI 草稿，不改变仓库 |

变更请求使用 Idempotency-Key 与 expected_revision。Idempotency-Key 只控制请求重发，不能代替业务批次/执行/仓库提交唯一约束。

## 4. 后端包接口

- `Connector.discover/inspect/extract` 返回 typed manifest，不直接入业务模型。
- `Profiler.profile(manifest, sampling_policy)` 返回统计与 evidence refs。
- `RuleCompiler.validate/compile` 产出冻结执行计划；`Runner.execute` 返回 output manifest+计数。
- `ModelCompiler.compile` 生成 SQL/dbt DAG；`Verifier` 执行关系/指标测试。
- `Publisher.prepare/commit/rollback` 独占 warehouse release 变更边界。
- `AIAssistant.recommend(context, task, output_schema)` 不持有提交权限。
- `QueryGateway.authorize/compile/execute` 权限由服务端 identity 提供，不由 LLM 参数提供。
- `BlobStore.put/finalize/open/delete_by_retention_policy` 无任意路径访问。

## 5. Excel 切到数据库/API

保持 stream ID/逻辑 schema 契约和下游模型不变，创建新的 connector/mapping version；仅物理来源变化时无需重写指标。

必须验证：粒度、标识、null/枚举、金额精度、时区、提取范围、一致性截止点、更新/删除/迟到、并行对账与回退。若这些含义改变，就是契约改变，不承诺“一键切换”。来源无稳定主键不能因换成数据库就假设天然可 upsert。

## 6. 示例与实施边界

`examples/synthetic-platform-plan.json` 描述一个两输入销售任务和一个独立客服任务，证明平台不以物流专用字段为中心。它不是生产配置或业务记录。

`contracts/ai-recommendation.schema.json` 为设计期产物，只覆盖类型/格式建议最小子集。P0 已实现项目基础策略契约（`packages/contracts/arp_contracts/schemas/project-policy.v1.json`）、基础身份/项目/配置 API（`contracts/control-api.v1.yaml`）及第一份迁移；尚未完成 PG/Redis 实机验收。完整 rules/model/metric DSL 和上表中的后续业务 API 仍按阶段实现，不把设计草案或示例验证通过当成接口服务可用。
