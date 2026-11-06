# 控制面与 API

状态：P0 基础代码已实现，本机测试通过；PostgreSQL/Redis/Compose 实机联调未验收。不是完整数据平台。

- `arp_control` 是可安装 Django/DRF 包，入口 `python -I -m arp_control.cli`；请先在独立环境安装根项目。
- 真实账号/会话/CSRF、持久化登录节流、UUID 项目/成员/角色、配置版本、幂等请求、revision CAS、事务审计。
- 只启用已实现的基础 API，见 `contracts/control-api.v1.yaml`。未实现的接入/运行/发布等接口不伪造 202 或成功结果。
- 运行配置只接受显式 PostgreSQL 和 Redis，不从旧项目或 SQLite 回退。测试 profile 仅用于隔离测试。
- 不在 HTTP 进程中执行转换、AI 或批量解析。任务状态、outbox 与数据引擎按 P1 后续实现。

本机验证、开发启动与限制见 [P0 记录](../../docs/10-p0-implementation.md)，全局实际状态见根 project.json。
