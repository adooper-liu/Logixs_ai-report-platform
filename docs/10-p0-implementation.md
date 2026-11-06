# 10 · P0 实施与验证记录

日期：2026-11-06。实际工作目录：`D:\Logixs_ai-report-platform`。本次继续原架构实施，没有迁入旧项目代码、数据、账号、密钥或运行环境。

**状态：P0 代码已落地，本机可验证部分通过；基础设施联调未验收，P0 尚未全部完成，未推进 P1。** `project.json` 的 `runtime_implemented=true` 仅表示 P0 控制面已有真实代码，不表示接入/加工/报表平台可用；`runtime_scope`、`platform_usable=false` 和阶段状态共同限定该标志。

## 1. 已实现

- 独立可安装 Python 包：`pyproject.toml`；运行、构建、开发三份带 SHA256 的依赖锁。保留 Django 5.2 LTS，不替换成其他后端。架构基线 Python 3.12，本机额外验证 3.14。
- 严格运行配置：显式 PostgreSQL URL、Redis URL、独立 Django secret、绝对 BlobStore 路径；无隐式 SQLite 回退、无自动读取旧环境。P0 拒绝启用 AI 和原始样本外发。
- Django/DRF 控制 API：UUID 账号、会话、CSRF、数据库持久化登录节流、项目、成员/组合角色、配置版本、审计、健康检查。账号创建仅平台管理员；来源描述不参与强制审核。
- 真实数据库迁移：账号、项目、Membership/RoleGrant、配置版本、幂等请求、审计、登录节流；唯一约束和合法角色检查。另有 PG 专用权限收紧迁移，撤销 control_app 对配置历史/审计的 UPDATE、DELETE；这部分仍待真实 PG 验证。
- 项目隔离：按授权范围查对象；外项目返回 404；viewer/operator/modeler/publisher/project_admin 能力分离；project_admin 不自动取得数据查看或发布权限；平台管理员仅由 Django superuser 表示，不可通过项目角色提升。
- 变更事务：`Idempotency-Key`、请求 HMAC、当前权限复核、`expected_revision` CAS、项目行锁、写入与审计/幂等回执同事务；移除最后一名有效项目管理员被拒绝。
- 不可原地修改的项目策略版本：封闭 JSON Schema v1、确定性指纹、创建新版本而非更新旧版本。这里只实现项目基础策略，不冒充完整 rules/model/metric DSL。
- LocalBlobStore：UUID 项目/key、大小限制、checksum、临时对象、原子且不覆盖的 finalize、空对象保留、只读打开和内容复核。不暴露上传或任意路径 API；不等同 P1 原始对象登记/manifest。
- 开发 Compose：PostgreSQL 17、Redis 8.2、迁移进程与非 root API；三个独立 DB、独立 owner，control_app 无 DDL/跨 DB 权限。镜像 index digest 已从 Docker Hub 公共元数据取得并锁定，**未拉取或运行验证**。
- OpenAPI：只包含本次真实实现的 API；离线核对路径、HTTP 方法与内部引用。后续接入/AI/发布接口不伪造成功响应。
- CI 文件：Python 3.12/3.14 测试、依赖扫描、Compose/PostgreSQL/Redis 集成步骤。文件已检查，未提交、推送或在外部 CI 执行。

## 2. 本机实际验证

开始实施前：原规划校验 PASS，原有 10 项规划回归全部通过。

实施后的命令（项目根目录）：

```powershell
.\.venv\Scripts\python.exe -I tools\validate_plan.py
.\.venv\Scripts\python.exe -I -m unittest discover -s tests -p test_plan.py -v
.\.venv\Scripts\python.exe -I tools\control.py --sqlite-tests test tests/control --verbosity 2
.\.venv\Scripts\python.exe -I tools\control.py --sqlite-tests makemigrations --check --dry-run
.\.venv\Scripts\python.exe -I tools\check_foundation.py
.\.venv\Scripts\python.exe -I -m pip check
.\.venv\Scripts\python.exe -I -m pip_audit --disable-pip --no-deps -r requirements.lock -r requirements-build.lock
```

- 规划回归扩展为 13 项：加入运行范围、提前标记 P0 完成及实施证据缺失的负例。规划检查仍然只证明结构一致性。
- 控制面测试使用**显式测试配置和临时 SQLite 数据库**；覆盖真实 ORM/迁移、权限、CSRF、登录节流、回执、版本冲突、事务失败回滚、BlobStore、策略 schema、健康检查。
- HTTP 测试使用临时 loopback Django 测试服务器，实际走 cookie/CSRF/登录/建项目/幂等重放；不是固定响应 mock，也不是持久运行或生产部署。
- 3 项 PostgreSQL 测试和 1 项 Redis 测试因服务不可用明确跳过；本机无创建 symlink 权限，相应拒绝测试也跳过。**跳过不计作通过。**
- 依赖 `pip check`、Ruff、Pylance 对控制 API/配置的语法检查通过；运行/构建锁的公开漏洞库扫描未发现已知漏洞。扫描只查询公开包名/版本，不提交业务数据。未完成镜像扫描或组织许可证审查，不承诺“无漏洞”。
- 镜像 registry 直接请求最初被连接重置；改用 Docker Hub 公共 tag 元数据取得 index digest。锁定元数据不代表容器运行通过。

本轮最终结果：规划回归 **13/13 通过**；控制面测试 **44 项，39 通过、5 跳过、0 失败**。迁移漂移检查无变化，独立 wheel 构建成功，数据库初始化脚本 shell 语法检查通过；本机 loopback 5432/55432/6379/56379 均未监听。完整命令输出及 `project.json` 记录的范围共同构成本轮证据；后续改动应重新测试，不把本文视为永久认证。

## 3. 环境阻塞与未验证项

- 当前没有 Docker 命令，也没有发现可用的 PostgreSQL/Redis 命令或服务；未安装 Docker Desktop、启用 WSL2或修改系统服务。
- 当前项目/Pylance 解释器是独立 `.venv\Scripts\python.exe`，Python 3.14.7；Python 3.12 的实际安装、依赖解析与执行尚未验证。
- 未运行 Compose build/start、新机器冷启动、Linux BlobStore 卷权限测试、PG 正反迁移、PG 并发 CAS/幂等及实际数据库角色隔离、Redis 认证联调。
- `.github/workflows/p0.yaml` 尚未运行；锁文件在 Windows/Python 3.14 生成，跨平台与 Python 3.12 安装仍以 CI/实机结果为准。
- LocalBlobStore 依赖私有目录 ACL、支持硬链接的本地文件系统；不声称防御拥有同目录写权限的恶意本机进程。解析进程沙箱、对象保留删除任务、生产 S3 后端属于后续实现。
- Redis 8.2 多许可证选项须由组织审查；开发 Compose 不是可直接上生产的安全/TLS/备份方案。

## 4. 无 Docker 时可以做什么

可继续代码、契约和显式 SQLite 测试，但不能把 P0 标为全验收。也可以在获准环境使用原生 PostgreSQL/Redis，Docker 不是应用代码依赖；本次不自行安装系统服务。不要为消除环境阻塞，把控制数据库改成 SQLite 或接入旧项目库。

## 5. 在有 Docker 的环境补齐验收

仅使用独立项目与合成数据。准备 Python 3.12 和支持 Linux 容器的 Docker Compose v2；保护生成 `.env` 的文件权限。以下创建环境的步骤仅用于**全新检出目录**；不要在现有 Python 3.14 `.venv` 内原地重建或覆盖环境，应另建环境并相应替换命令路径。

```powershell
# 在本项目根目录，使用独立 Python 3.12 venv
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -I -m pip install --require-hashes -r requirements-dev.lock
.\.venv\Scripts\python.exe -I -m pip install --no-deps --no-build-isolation -e .
# 文件已存在时工具会拒绝覆盖，不要因此删除现有凭据或数据库卷。
.\.venv\Scripts\python.exe -I tools\init_dev_env.py --output .env
.\.venv\Scripts\python.exe -I tools\resolve_images.py --from-lock infra\images.lock.json --env-output .env.images

docker compose --env-file .env --env-file .env.images -f infra/compose.yaml config --quiet
docker compose --env-file .env --env-file .env.images -f infra/compose.yaml up --build --wait --wait-timeout 240
.\.venv\Scripts\python.exe -I tools\verify_p0_services.py --env-file .env
# 交互创建本项目管理员，密码不放命令行，不提供默认账号。
docker compose --env-file .env --env-file .env.images -f infra/compose.yaml exec control python -I -m arp_control.cli createsuperuser
```

集成工具限定 loopback 开发环境；使用 bootstrap 只在隔离测试库中建库/运行测试。控制 API 仅获得 `control_app` 凭据；迁移进程仅获得 `control_owner` 凭据。`/health/live` 是存活检查；`/health/ready` 必须在 DB/迁移/Redis/BlobStore 都通过时才返回 200。

已有 Compose 卷不会重新执行 init 脚本。`.env` 丢失或凭据变更时不要盲目删除卷；保留数据并单独处理凭据轮换。停止服务不删除卷：`docker compose --env-file .env --env-file .env.images -f infra/compose.yaml down`。

原生服务使用者可显式执行：

```powershell
.\.venv\Scripts\python.exe -I tools\control.py --env-file .env --migration-role migrate
.\.venv\Scripts\python.exe -I tools\control.py --env-file .env createsuperuser
.\.venv\Scripts\python.exe -I tools\control.py --env-file .env runserver 127.0.0.1:8000 --noreload
```

仅开发使用 runserver；数据库和角色须先按 `infra/postgres/init.sh` 在新建开发实例中初始化，不能对已有共享库盲目执行。

## 6. 下一会话起点

先读取本记录、`project.json` 与路线图。**继续实施，不重新规划，不退回文件登记工具。** 先补齐 P0 实际环境验收并修复发现的问题；全部通过后更新阶段状态，再开始 P1 多输入接入/规范闭环。P1-P5 的连接器、前端、执行引擎、outbox 调度、模型、仓库发布、AI、Superset 仍未实现。

本轮没有提交或推送代码，没有调用外部模型、迁入真实业务数据、部署外部服务或配置旧项目依赖。
