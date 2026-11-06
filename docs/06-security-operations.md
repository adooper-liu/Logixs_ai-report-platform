# 06 · 安全、部署与运维

## 1. 身份和权限

组织内先做 project-scoped RBAC，角色建议 viewer、operator、modeler、publisher、project_admin、platform_admin；可组合，不要求另一人审核。业务说明选填不代表所有人可改规则或发布。

- 普通 operator 接入/重跑被授权来源；modeler 编辑规则/模型；publisher 变更发布指针；数据查看授权独立。
- connection 使用和 secret 查看分开，UI 不提供回显密钥。
- 接口先做项目及对象权限，再取上下文/查数据。后端不可依赖前端隐藏按钮。
- 企业 OIDC/SSO 在试点阶段集成；本地管理员仅初始化/应急，密码策略、节流、会话和 CSRF 均需测试。
- 服务账号与人分开：来源只读、staging writer、model builder、publisher、BI reader；不复用超级用户连接。

## 2. Superset 与查询权限

Superset dataset 权限与 RLS 需与平台项目/角色映射，SQL Lab 对普通业务账号关闭或独立严格授权。不得只靠 Superset UI/RLS 当数据库防火墙。

普通业务数据集只暴露安全视图；数据库 grants、必要时 PostgreSQL RLS 是额外边界。使用共同 BI 连接账号时，PostgreSQL 不知道终端用户是谁，不能假设 current_user 自动区分各用户。安全方案必须选择并测试：按权限域独立连接/视图，或由可信查询网关以受控身份执行；不接受用户可改 session 变量来伪造身份。

问数走同一授权模型，不能拥有更宽的底层连接。缓存/导出含用户权限范围、policy version、dataset release，权限收回使缓存失效。先校验权限再查缓存。

## 3. 文件与连接安全

- 上传对象独立随机 key、checksum、大小/压缩/行列/处理时间配额；拒绝路径穿越、外部关系、宏执行、恶意公式。
- 解析器在低权限隔离 Worker 中运行，无平台密钥、无不必要网络；错误文件不进入应用代码目录。
- CSV 导出防公式注入，XLSX 公式单元格策略明确；不因“只读”就认为解析器无漏洞。
- DB/API/目录连接管理阻断 SSRF：允许网络目的地，控制 DNS/IP、重定向、端口，拒绝云元数据和未经授权 loopback/private endpoints；内网源通过管理员明确配置允许。
- 不通过 AI 工具直接执行 SQL、shell、pip 安装或访问随机 URL。

## 4. AI 数据外发

默认不发送原始工作簿。按 project policy 限制结构、摘要、脱敏样本，提示/响应和 trace 也按敏感数据管理；自由文本可能含个人信息，不因字段名普通就放行。

凭据来自环境或受控 secret store；`.env` 不提交。不使用旧项目密钥/账号。部署前明确供应商服务、数据地区、保留政策和组织许可，不能仅凭使用 SDK 推断合规。

模型请求 timeout/retry/concurrency/budget 全受限；拒绝/降级不假成功。模型不可用时已保存任务继续执行，配置者可手工提供规则。

## 5. 部署与版本

初期单 Linux 主机/小型 VM，预估资源只作为试验起点，需按实际文件规模和并发压测。对象存储、数据库卷、临时盘配额独立；解析、transform、AI workers 不互相抢完资源。

Python 基线 3.12 + Django LTS；实施时核验所有库兼容版本。依赖 lock、镜像 digest、SBOM/漏洞扫描、数据库迁移演练。Superset 自己的 Python 依赖用独立镜像，避免与平台的 SQLAlchemy/Flask 版本冲突。

开发可本地文件存储；部署对象存储具体产品及许可证在 P0 评估，不默认任何 S3 兼容产品都可无条件商用。平台与 Superset、各开源依赖许可证一起核对。

不一期引入 Kubernetes；只有跨机器调度、弹性和容灾需求明确时升级。

## 6. 运行可靠性

- DB outbox 补偿队列丢失，定时扫描未投递/过期 lease；Redis 清空可重建消息，不丢唯一任务状态。
- retry 只针对可重试故障。类型/规则错误 blocked，不无限重试；worker OOM/进程崩溃形成失败 attempt。
- 并发提交、网络断开、worker 重复投递、发布 ACK 丢失、取消与提交竞争均做故障注入。
- 资源控制：文件大小、解压大小、CPU、内存、磁盘、SQL statement_timeout、结果行数/字节数、AI 配额。
- 任务完成不仅是进程 exit=0，还要有 output manifest、计数、质量、提交记录；缺一个不能标记 published。

## 7. 监控和告警

日志统一 run_id、attempt、project、stage、schema/rule/model version、release、trace_id，记录错误码和安全定位，不记录原始凭据/大量明细。

指标：输入新鲜度/缺失、等待/运行时长、吞吐、隔离率、规则失败、重试/lease、队列积压、磁盘、仓库查询耗时、发布年龄、AI 费用/失败/缓存。告警合并与去重，避免每坏一行发一条消息。

## 8. 备份与恢复

分别保护 control DB、warehouse DB、原始对象/manifest、规则模型配置、Superset DB、密钥。元数据备份不等于业务仓库备份；同主机不同 DB 也不等于容灾。

试点拟定目标（尚未达成）：control/warehouse RPO <= 1 小时、RTO <= 4 小时；正式部署由业务与成本决定。使用定时备份+PITR 能力、加密异地备份、对象保留/版本策略。上线前实际演练，不把“有脚本”当恢复成功。

恢复以 warehouse manifest/active pointer 为权威对账 control 状态；原始对象缺失必须报告，不能仍声称可完整重放。备份恢复不撤销当前隐私删除和权限收回要求。

## 9. 保留与删除

原始层“不可改写”是版本不可原地编辑，不是永久不可删除。项目按敏感等级定义 raw/quarantine/release/日志/AI 请求保留期。受监管删除采用有权限的删除流程、血缘影响记录、对象与副本/备份策略，不允许发布回退重新暴露已删除数据。

只自动清理本 run 的临时对象；真正业务数据删除、覆盖和正式回退需要显式权限与配置范围，不从 AI 猜测发起。
