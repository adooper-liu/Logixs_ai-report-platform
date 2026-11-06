# 03 · 建模、指标与可靠发布

## 1. 三层业务能力与仓内分层不是一回事

业务能力三层是 L1 接入规范、L2 建模指标、L3 报表分析。仓内另按以下技术区域组织：

- 原始对象：不可改写的抽取文件/响应及 manifest，保留重放证据。
- `stg`：按 run 隔离的规范数据和错误隔离输出。
- `core`：规范实体、事实和维度，保持明确粒度及身份映射。
- `mart`：面向主题的数据集、可加性明确的聚合与指标。
- `pub`：BI 可访问的稳定发布接口，只暴露已发布 release。

不能用业务三层替代数据历史、暂存和发布边界。

## 2. 模型契约

模型定义包含 model_id/version、project/domain、输入 dataset/version、row grain、键候选与已验证约束、属性类型、关系、时间、增量策略、测试、权限、血缘。说明文本可为空；可执行粒度/关系若不明确，模型生成任务暂存为候选，不阻止来源接入。

模型类型：事实、维度、桥表、聚合、参考映射。明确自然业务键、来源记录定位、平台实体键的区别。公共维度按作用域/生效时间映射；未知值、无匹配、多匹配分别处理，不任取第一条。SCD2 是可选模型策略，不默认为所有实体保留有效期。

同一订单有多行商品不等于重复订单；多对多关系需桥表或明确分摊，不让金额在 join 后重复累计。

## 3. AI 辅助建模的确定性验证

AI 输出关系候选和依据，不直接向 PostgreSQL 执行 DDL。编译器检查字段引用、类型、DAG 和受限表达式，试运行测量：

- 候选键全量唯一性、null 与范围覆盖；抽样唯一率不等于约束证明。
- 每侧 key multiplicity、匹配/未匹配/多匹配计数。
- 关联后扩张倍数、重复贡献、被过滤行，按实际关联类型对账。
- 金额、数量及 distinct 身份等守恒/差异解释。
- 缺失维度、有效期重叠、同一实体多来源冲突。

一对多不默认错误；只有与声明关系/指标粒度不符才阻断。domain 模型各自测试，不强迫所有数据都遵守“包裹”或“订单”身份。

## 4. SQL/dbt 执行边界

平台模型/指标契约是唯一编辑源，编译产物（dbt SQL、schema tests、文档、BI 数据集）有 digest，不能反向任意编辑而仍称同步。

一期支持受限 select/filter/join/group/aggregate、引用已有模型、受限表达式，编译至 dbt/PostgreSQL。dbt 负责依赖构建和测试，平台负责租户/项目权限、输入版本和发布状态。dbt 执行采用候选 schema/release_id，不能直接覆盖 BI 当前表。

复杂专家 SQL 为后续能力：独立权限、AST 约束、只读输入、隔离目标 schema、资源上限、测试与版本。仅做 SELECT 字符串检查不安全，允许 SQL 也不能绕过数据库角色与表级授权。

## 5. 指标语义

Metric 至少含：ID/version、模型/行粒度、表达式 AST、度量类型、分子/分母、分组维度、时间字段/时区/日历、过滤、null/除零策略、可加性、币种/单位、适用范围。

- ratio = sum(numerator)/sum(denominator)，不能平均分组百分比。
- distinct count、余额、库存等不可任意跨维度/时间相加。
- distinct 指标若支持近似算法必须显式标记，不能默默替代精确值。
- 金额币种转换需要汇率来源/日期/版本，AI 不凭常识补汇率。
- “订单数”不能在未明确粒度时用 COUNT(*) 冒充。

指标草稿可保存，无强制人工审批；正式对外服务需要依赖与自动测试通过，或按预设策略由有发布权限者应用配置。业务歧义只阻断相关指标，不冻结整个平台。

## 6. ReleaseBundle 与一致性

一个主题 release 包含全部相关 dataset output manifests、schema、规则/模型/指标/字典版本、输入批次、质量摘要、checkpoint 和权限策略版本。订单、明细、产品等不能分别切换导致半新半旧。

流程：

1. 固定所有输入版本与 cutoff，运行至独立 staging/candidate release。
2. 完整模型/质量检查，通过后标记 ready。
3. 将输出写为不可改写的 release 数据分区/快照，记录 checksums。
4. **在 warehouse 单个事务中**登记 release manifest、更新主题 active pointer，必要时原子更新稳定视图。
5. warehouse outbox 记录提交事件；control DB 异步同步发布状态；任务成功才推进对应 committed checkpoint。

权威发布状态在 warehouse。两个数据库间没有隐含分布式事务：若 warehouse 已提交、control ACK 丢失，重试通过 release_id 识别已有提交并恢复。禁止依据 control 单方面标记 published 后让 BI 看到不存在的数据。源 checkpoint 同样需提交对账/恢复。

一个共享源为多个下游使用时，接入抽取 checkpoint 与各消费 pipeline processed checkpoint 分开，不因某报表失败删除原始已接收数据。

## 7. BI 查询与回退

Superset 使用只读账号，仅授权 `pub`，不访问原始对象、staging、控制库或模型候选。发布时 schema 兼容检查；删除/改类型破坏兼容时另建数据集版本，不静默破坏已存在报表。

单条查询读取同一 release 的稳定数据。**Superset 一个 dashboard 会发送多条查询，默认不保证所有图表同时切换。** 一期报表展示 release ID/数据更新时间；要求严格整页一致时，采用固定 release 的数据集或语义网关将 release 参数绑定到全部查询，缓存键也含 release。禁止宣称改一个指针就能保证所有浏览器图表瞬时一致。

缓存失效/版本化纳入发布步骤；旧结果即使合法也不能无标识混同新数据。订阅导出绑定 release，过期会话/权限再次检查。

回退是切换 active pointer 到保留的历史 release；不是倒改来源或原地重算。保持其完整依赖和权限可用性，记录操作者/原因。权限收回或 PII 删除要求不能因回退被撤销。RLS/安全策略从当前授权施加，而非直接恢复历史授权。

## 8. 血缘和追溯

最小必须：报表/指标 -> release -> model/rule version -> input batch -> 原始对象/checksum。字段级血缘由编译器引用生成。

逐行 lineage 对 filter/rename 易得，对 join/聚合可能是一组输入；使用 key/partition/index/lineage reference 按需追溯，不为每条聚合结果保存庞大的全展开行 ID 列表。界面说明可追溯粒度，不能只有一列“来源文件”就声称完整血缘。
