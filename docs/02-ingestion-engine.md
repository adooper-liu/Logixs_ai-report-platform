# 02 · 数据接入与确定性引擎

## 1. 不是“一个文件一个来源”

- Connection：目录、数据库或 API 连接，包含凭据引用而非密钥。
- Source：稳定来源实例，例如某系统某组织环境。
- Stream：来源中的逻辑数据流，例如订单、订单明细、产品字典；可对应多个分片文件/工作表/抽取分页。
- Batch：某 stream 的一次提取，可有 0、1 或多份输入，显式记录是否完整。
- RunGroup：一次模型生产所需的多个 stream 批次集合，绑定截止点、参数与依赖。

文件名只是定位辅助。content hash 用于对象去重，不等于业务批次身份；相同内容可能属于不同声明范围。跨来源同 hash 不等于相同记录。

## 2. 接入器统一协议（待实现）

`discover -> inspect -> extract -> materialize manifest -> commit checkpoint`

统一输出 `BatchManifest`：project/source/stream IDs、adapter/version、extract_id、schema_fingerprint、原始对象清单/checksum、抽取起止、范围、更新模式、snapshot token 或 watermark、输入完整性、记录计数证据。源更新时间缺失时为空，不用接收时间伪造。

每行附 `record_locator`：文件 ID+工作表+行号，或数据库抽取 ID+来源主键，或 API request/page/record locator。locator 是证据定位，不一定是业务实体主键。若源无主键/快照保证，显式降低可重放/增量保证。

### 文件/目录

- `.xlsx`、CSV 优先，Parquet 随后；支持多选、目录收集、多 sheet 和分片 manifest。
- 先上传临时对象，校验完成再 finalized；目录用 ready manifest/原子 rename 或稳定性协议，禁止读半文件。
- 表头识别、Excel 1900/1904 日期体系、单元格格式、公式/缓存值、超长数字精度均有独立策略；不执行宏、不默认计算公式。
- 多行表头、合并单元格或重复列名：给出位置式内部 column_id 和修正建议，无法唯一映射时不建立正式规则；原始文件仍可保存。
- 文件来自上传、网络共享或目录都通过同一 BlobStore/manifest，不让 Worker 按任意路径扫描。

### 数据库

一期先支持 PostgreSQL 只读 full/范围抽取，再扩展其他驱动。白名单 schema/表/列，分页排序稳定，显式一致性快照；大事务对来源负载有预算。

增量 watermark 使用稳定 tie-breaker，包含相同更新时间多行、重叠窗口和来源删除策略。读取成功不立即推进已提交 checkpoint；下游提交成功后按任务协议推进。CDC 后续单独接入，不能把时间戳轮询称为可靠删除捕获。

### API

固定允许域名、连接模板、分页规则、超时、限流、重试、request ID；完整分页证据落 manifest。没有稳定快照或游标时明确标记一致性限制。禁止 AI 生成任意 URL 携带凭据访问内网。

## 3. 多来源就绪与时间一致性

每任务声明 input roles、required/optional、同范围匹配、cutoff、允许迟到、完整性证据、超时、降级策略。

例：合成销售模型需要订单+明细，产品字典可使用上一个明确版本。字典复用必须写入 release，不隐藏“本次”实际用了旧输入。缺少明细时等待或 fail；不因已有订单就宣称整批完整。

零条记录不等于缺失输入。只有来源明确确认范围为空、分页完成/快照完成，才视为空批次完成。文件最早/最晚日期不是范围覆盖证明。

迟到输入：创建新 run/release，不修改已发布 release 的输入清单。backfill 明确分区，不能误覆盖全表。

## 4. 本地剖析与类型体系

规范类型：string、identifier、boolean、int64、decimal(precision,scale)、date、local_datetime、instant(UTC)、json（受限对象）、binary reference。

- 编号、邮编、电话可数字外观但按 identifier/string；已丢失精度或前导零不可自动恢复。
- 金额用 Decimal，不默认 float；溢出/舍入规则必须明确。
- `03/04/2026` 不能自动定为 3 月 4 日；保留歧义候选。
- naive 时间不自动赋 UTC；先 local_datetime，配置来源时区后再转换；DST 重复/不存在时间有错误策略。
- identifier trim、大小写折叠、unicode 规范化也可能改变键，只在配置允许时执行。
- 抽样剖析标注 sample_count、抽样方式、覆盖范围；全列验证另行运行。样本全空不能确认类型。

剖析输出统计和证据引用：类型比例、空值、长度/分位数、异常样式、候选唯一率等。敏感样本默认不进入 AI 请求或普通日志。

## 5. 规则 DSL

不是自由 Python/SQL。规则节点包含 `operator`、输入列 ID、显式参数、失败处理、输出类型、适用范围、版本。操作白名单：select/rename、cast、parse_date/datetime、trim、null_map、enum_map、derive（受限表达式）、filter、split、reference_lookup、dedupe（显式键和选择规则）。

每个操作定义 null 传播、类型、排序、精度、locale/timezone 和错误语义。规则编译前做 schema/类型/DAG 校验；SQL 标识符/字面量分离；列来源不得靠位置漂移默默改变。规则运行结果绑定引擎、包锁、模板/规则/参考字典版本和随机种子（若有）。

处理异常的策略：fail_batch、quarantine_row、keep_raw_with_issue；由规则配置。禁止默认忽略失败行、默认空值填 0、默认按首条去重。

无规则时只做安全解析、原始留存和无损规范暂存；不能替用户猜 upsert/删除/货币转换。正式写入模式未配置则不提交目标表，但不阻止原始接收。

## 6. 质量与守恒

检查类型、可解析性、必填、范围、枚举、唯一性、外键、行数变化、跨来源对账、异常比例和新鲜度。每条 rule 有 severity、action、threshold 和 scope；默认策略可复用，不等于要逐条人工审批。

记录守恒：input = accepted + quarantined + explicitly_filtered，若 explode/join/dedupe 另有扩张/归并计数和谱系。保存每步输入/输出/失败数，不能只写“通过”。

错误表含 run、rule、column_id、record locator、错误码及受保护的原始值引用。大批错误使用汇总+分页，不能把全量敏感行塞日志。隔离数据只允许授权角色查看。

## 7. 执行与重试

阶段状态：`waiting_inputs -> queued -> running -> validating -> staged -> committed`；异常状态 failed/cancelled/blocked，单独保存 stage+attempt。发布任务另有 `publishing -> published`。状态转换事务、lease/heartbeat、重试次数均持久化。

DB outbox 与 Run 创建同事务，dispatcher 可重复投递；Worker 取得 lease 才执行。锁过期重试不等于杀死旧写入：commit 使用 fencing token/current attempt，旧 Worker 无权提交。取消是协作取消；未提交阶段删除自己临时对象，不动已发布数据。

幂等键分开：

1. 接收：source/stream+extract ID 或 manifest hash+范围+提取策略。
2. 执行：输入 manifest IDs+规则/模型/字典版本+参数+引擎版本。
3. 提交：目标 dataset+run/attempt token+输出 manifest，唯一约束。

系统保证可重试与幂等提交，不宣称跨来源 exactly-once。相同规则重跑要复用或生成可解释替代版本，不能重复 append。

## 8. 入仓模式

- append：需要可重试的事件身份或平台提交分区；无业务唯一键时保留原始重复，不擅自删除。
- full_snapshot：仅替换明示范围，必须确认提取完整。
- partition_replace：显式 partition predicates，空批次删除分区也需要完整性证据。
- upsert：明确业务键、来源版本排序、删除/tombstone、迟到/相同版本冲突策略。

staging 以 run_id 隔离；合格后仓库事务提交，失败不改变有效分区/checkpoint。长期模型历史与入仓增量策略分开；对 mutable 基表若要完整历史，必须保存版本/快照，不能依赖旧表自动还在。
