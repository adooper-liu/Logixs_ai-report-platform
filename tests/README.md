# 测试边界

状态：规划回归及 P0 控制面/契约/存储/HTTP 测试已实现；PostgreSQL/Redis 集成测试已编写但本机环境缺失，明确跳过，不计通过。

- `test_plan.py`：规划/实施清单结构一致性、边界、负例；不证明服务可用。
- `control/test_foundation.py`：ORM/API、角色与跨项目隔离、revision/幂等、版本、事务/审计回滚。
- `control/test_auth.py`：真实 Django session、CSRF、登录节流、停用账号、Origin 拒绝。
- `control/test_config_blob.py`：严格配置、封闭策略 schema、checksum/配额/空对象、路径隔离与不覆盖。
- `control/test_http.py`：真实 loopback 临时 HTTP 测试服务器上的登录、项目创建和重放；不属于生产部署。
- `control/test_health.py`：存活/就绪区分、依赖失败不伪成功、最小健康信息披露。
- `control/test_postgres.py`：仅真实 PG 的并发 CAS/幂等、正反迁移；Redis 实际 ping 需要 `P0_REQUIRE_SERVICES=1`。使用独立测试库，禁止生产库。

本机命令：`python -I tools/control.py --sqlite-tests test tests/control`。SQLite/MD5 快速哈希只在命名明确的测试设置中启用，不可用于服务运行或充当 PG 验收。symlink 测试在 OS 不授权创建链接时也必须明确标记跳过。

真实环境验收：`python -I tools/verify_p0_services.py --env-file .env`，前提见 docs/10-p0-implementation.md。P1 多输入/崩溃/重复投递、数据质量、模型/发布、AI 与 BI 测试尚未实现，不得用 P0 测试代替。
