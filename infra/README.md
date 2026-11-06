# 部署基础设施

状态：P0 开发配置已实现，未在本机运行；没有 Docker/PG/Redis 环境，不能宣称新机器启动验收通过。

- `compose.yaml`：仅开发使用，PG 17、Redis 8.2、迁移进程和非 root 控制 API；仅 loopback 映射端口。
- `images.lock.json`：已从 Docker Hub 公共元数据解析的不可变 index digest，不使用 latest；`runtime_verified=false`。
- `control.Dockerfile`：Python 3.12 基础镜像、hash 锁依赖、独立安装包；服务内不带旧项目目录或环境。
- `postgres/init.sh`：只针对全新开发卷；control/warehouse/superset 三库及独立账号。control_owner 负责迁移，control_app 只做 DML，无 DDL/跨库权限。
- BlobStore 使用专用本地卷；生产对象存储、TLS、备份、监控及许可证组织审查尚未完成。
- Superset 仍是后续 BI 组件，本阶段只为其保留独立元数据库，不启动或假装集成完成。不会改成 Metabase。

独立凭据生成、镜像环境文件、启动命令及真实服务验收见 [P0 实施记录](../docs/10-p0-implementation.md)。生成工具拒绝覆盖现有凭据；不要通过删除数据库卷“解决”凭据错误。

CI 工作流已提供但未提交/推送/执行。本轮无任何外部服务部署。
