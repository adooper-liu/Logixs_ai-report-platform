# AI Report Platform · 通用报表数据平台

> 当前交付：架构与规划包，以及 **P0 控制面基础代码、迁移、权限 API、配置契约和测试**。**P0 基础设施联调未验收，不是可用的完整报表平台。** 实际阶段状态见 `project.json` 与[实施记录](docs/10-p0-implementation.md)。

当前工作目录：`D:\Logixs_ai-report-platform`；项目支持搬迁，运行不依赖该绝对路径。不依赖原物流项目运行目录、虚拟环境、账号、数据库或 V6 程序。

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
| [规划包验证记录](docs/09-planning-verification.md) | 初始规划包校验，保留历史范围 |
| [P0 实施与验证](docs/10-p0-implementation.md) | 本轮实现、复现命令、环境阻塞与下一步 |
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

P0 已安装 Django/DRF 等基础依赖并落地开发 Compose，镜像 digest 已锁定；当前没有 Docker/PostgreSQL/Redis 可供运行联调，因此不声称 Compose 已可用。其他组件仍是选型，不代表已安装、许可证已完成组织审查或集成已验证。

## 项目结构

```text
apps/control/           Django 控制面、账号/项目权限、配置版本 REST API（P0 待联调验收）
apps/web/               React 工作台（待实现）
workers/                调度、任务执行、AI 任务（待实现）
packages/connectors/    文件、目录、数据库、API 接入（待实现）
packages/profiling/     本地数据剖析（待实现）
packages/rules/         规则 DSL 校验、编译、执行（待实现）
packages/modeling/      粒度、关系、指标编译与验证（待实现）
packages/ai/            模型调用、上下文、建议验证（待实现）
packages/contracts/     P0 项目策略 JSON Schema、离线校验与指纹（后续 DSL 待实现）
warehouse/dbt/         编译模型与测试（待实现）
infra/                  开发 Compose、数据库初始化、不可变镜像引用（待实机验证）
tests/                  规划、控制面/HTTP/BlobStore 测试；PG/Redis 集成待实测
contracts/              设计期 AI 最小契约和 P0 OpenAPI
examples/               明确标记的合成规划示例，不含真实业务记录
tools/                  规划/基础工程校验、显式配置加载和集成验收工具
```

## 本机验证与运行

已有项目独立 `.venv` 的环境中：

```powershell
Set-Location D:\Logixs_ai-report-platform
.\.venv\Scripts\python.exe -I -m pip install --require-hashes -r requirements-dev.lock
.\.venv\Scripts\python.exe -I -m pip install --no-deps --no-build-isolation -e .
.\.venv\Scripts\python.exe -I tools\validate_plan.py
.\.venv\Scripts\python.exe -I -m unittest discover -s tests -p test_plan.py -v
.\.venv\Scripts\python.exe -I tools\control.py --sqlite-tests test tests/control
.\.venv\Scripts\python.exe -I tools\check_foundation.py
```

无独立环境的新机器先用 Python 3.12 创建 `.venv`；不要使用旧项目环境。现有本机是 Python 3.14.7，不能视为 3.12 已验证。

没有 Docker 不影响以上开发测试，但显式 SQLite 测试不能证明 PostgreSQL 的并发、权限、迁移和 Redis 集成。服务运行必须显式配置 PostgreSQL/Redis，不会回退 SQLite。开发 Compose 启动、管理员初始化及真实服务验收见 [P0 实施记录](docs/10-p0-implementation.md)。**本轮未启动这些服务，未宣称全平台可用。**

## 下一实施起点

先补齐 P0 独立基础设施实机验收，通过后再推进 P1 两来源接收、规范和安全提交，不重新规划，也不退回来源登记工具。之后按原路线推进 AI、建模指标与 Superset；三层产品边界不变。

没有复制原项目的运行数据、密钥或业务算法，也没有修改原项目。未调用外部模型，未发生本项目 AI 推理费用。
