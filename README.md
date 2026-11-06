# AI Report Platform · 通用报表数据平台

> 当前交付：技术框架、接口与契约设计、分阶段实施计划、示例及规划校验工具。**不是已实现或部署的平台。**

独立项目根目录：`D:\ai-report-platform`。不依赖原物流项目运行目录、虚拟环境、账号、数据库或 V6 程序。

## 目标

**AI 辅助建立规则和模型，确定性引擎持续生产数据。**

- 多来源：批量文件、目录、数据库、API；来源不是单个上传文件。
- 三层：接入与规范、业务建模与指标、报表与分析，AI 贯穿三层。
- 业务说明选填，无强制登记问卷、无逐文件人工审核流程。
- 可执行规则必须明确；不根据 AI 猜测自动去重、覆盖、改指标口径。
- 原始数据可追溯，批次可重跑，版本可回退，失败不影响上一有效发布。
- 支持销售、库存、客服、财务等不同业务域；不内置物流 V6 逻辑。

## 阅读路径

| 文档 | 解决的问题 |
| --- | --- |
| [完整技术架构](docs/01-architecture.md) | 三层、技术选型、模块、部署拓扑和界面 |
| [数据接入与确定性执行](docs/02-ingestion-engine.md) | 多输入批次、清洗、质量、增量、幂等、执行状态 |
| [模型、指标与发布](docs/03-modeling-publication.md) | 粒度、关联、语义目录、跨表一致性、原子切换和 BI |
| [AI 能力框架](docs/04-ai-framework.md) | 三层 AI、输入输出、验证、脱敏、成本和评测 |
| [数据对象与 API](docs/05-contracts-api.md) | 元数据对象、接口契约、来源切换和版本策略 |
| [安全、部署与运维](docs/06-security-operations.md) | 账号隔离、查询安全、备份、告警和容量 |
| [实施路线与验收](docs/07-roadmap.md) | 六个实施阶段、完成条件和首个交付切片 |
| [现有内容复用清单](docs/08-reuse-boundary.md) | 哪些可提取、哪些不得迁移、如何验证通用性 |
| [规划包验证记录](docs/09-planning-verification.md) | 本次实际检查、环境与未验证范围 |
| [核心架构决策](docs/adr/0001-foundation.md) | 选择理由、替代方案及升级触发条件 |

## 拟定技术栈

- 控制面：Python 3.12、Django 5.2 LTS、Django REST Framework。
- 前端：React + TypeScript + Vite；中文任务工作台，不以来源登记表为中心。
- 调度：Celery + Redis；PostgreSQL 保存权威运行状态和 outbox，Redis 不保存唯一状态。
- 处理：Arrow/Parquet、Polars；DuckDB 作为单任务 SQL/关联执行器，不作为多人共享数据库。
- 模型：受约束的模型/指标契约，编译到 PostgreSQL SQL 与 dbt Core；不直接执行任意 AI 代码。
- 数据：PostgreSQL 元数据库、仓库、Superset 元数据库逻辑隔离；原始对象采用存储接口，开发本地、生产 S3 兼容存储。
- AI：统一内部接口，首个提供方使用官方 Anthropic Python SDK；不在前端持有密钥。
- BI：独立部署 Apache Superset，只读访问发布层；问数通过语义与权限网关。
- 部署：开发 Windows + WSL2/Docker，试点及生产 Linux；版本与镜像 digest 在各阶段实现前验证、锁定，不用 `latest`。

以上为选型，不代表依赖已安装、许可证已完成组织审查或集成已验证。当前不生成伪可运行的 Compose/后端入口。

## 项目结构

```text
apps/control/           Django 控制面和 REST API（待实现）
apps/web/               React 工作台（待实现）
workers/                调度、任务执行、AI 任务（待实现）
packages/connectors/    文件、目录、数据库、API 接入（待实现）
packages/profiling/     本地数据剖析（待实现）
packages/rules/         规则 DSL 校验、编译、执行（待实现）
packages/modeling/      粒度、关系、指标编译与验证（待实现）
packages/ai/            模型调用、上下文、建议验证（待实现）
packages/contracts/     运行时契约与配置 schema（待实现）
warehouse/dbt/         编译模型与测试（待实现）
infra/                  镜像、部署、数据库初始化（待实现）
tests/                  回归与集成测试（待实现）
contracts/              当前已提供的设计期机器可读契约
examples/               明确标记的合成规划示例，不含真实业务记录
tools/                  规划包校验工具
```

## 本次可以验证什么

安装独立的规划校验依赖，不使用旧项目 `.venv`：

```powershell
Set-Location D:\ai-report-platform
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-plan.txt
.\.venv\Scripts\python.exe -I tools\validate_plan.py
```

此命令仅验证 JSON 规划结构、示例、文档链接与项目边界；不连接业务数据库、不调用 AI、不启动 Superset、不等于平台验收。

## 实施起点

先完成 P0/P1：独立基础设施、契约与两来源接收、规范和安全提交，再接入 AI 规则建议。随后完善建模、指标与 BI；三层接口从第一阶段就按整体架构设计。详见路线图。

没有复制原项目的运行数据、密钥或业务算法，也没有修改原项目。未调用外部模型，未发生本项目 AI 推理费用。
