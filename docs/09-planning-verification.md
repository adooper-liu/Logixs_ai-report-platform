# 09 · 规划包验证记录

验证日期：2026-11-06。对象为技术框架文档、目录边界、设计期 schema 和合成示例，不是平台运行验收。

> 本文保留最初规划包交付时的历史状态。后续 P0 实施与实际路径、验证结果以 [P0 实施记录](10-p0-implementation.md) 和 project.json 为准；以下“尚无后端”等描述不再代表当前代码状态。

## 环境

- 独立根目录：D:\ai-report-platform。
- 独立 .venv；实际规划校验解释器 Python 3.14.7，jsonschema 4.26.0。
- 架构拟定的应用运行版本是 Python 3.12；本次未安装和验证该运行栈，不能以规划脚本通过替代兼容性测试。
- 仅安装 requirements-plan.txt 中的校验依赖，无外部 AI 请求、业务数据库连接或 BI 服务。

## 执行与结果

从独立项目根目录执行：

```powershell
.\.venv\Scripts\python.exe -I tools\validate_plan.py
.\.venv\Scripts\python.exe -I -m unittest discover -s tests -p test_plan.py -v
```

结果：规划校验 PASS；10 项规划校验回归测试通过。

校验内容：

- 项目状态保持 architecture_planned，未实现/未生产标志准确。
- 清单中的模块目录、边界说明、文档、schema、示例存在；本地文档链接有效；清单路径不能逃出项目。
- AI 建议满足最小 JSON Schema；拒绝任意 Python operator、额外代码字段和直接执行授权声明。
- 建议 ID 唯一；最小 operator 参数语义、Decimal 精度/小数位和影响分类检查。
- 合成销售、客服两域的 stream/model/metric/pipeline 引用按项目隔离，示例无强制业务审核。
- 工单 full_snapshot 与事件 append 分别指定范围/完整性或幂等身份，避免把事件键用于工单快照。

10 项回归测试：有效包、跨项目输入、虚假运行完成标志、越界路径、坏文档链接、快照范围缺失、重复建议 ID、错误 Decimal 参数、append 幂等身份缺失、强制审核。均使用临时副本，不改写正式规划示例。

## 不能据此宣称的能力

- 尚无后端/前端服务、调度器、连接器、清洗执行器、共享仓库或 Superset 集成。
- 尚未运行任何业务流水线、模型 SQL、AI 效果评测或真实性能/灾备/安全验收。
- 当前 schema 仅覆盖规范建议子集；证据/列 ID 与真实画像的对应、模型语义正确性、完整规则 DSL 仍须后续实现验证。
- 合成配置是规划示意，不是已经能被生产执行器读取的配置。
- 未把原项目代码、运行库、账号、密钥、真实数据或 V6 算法迁入本项目。

实施仍须按 docs/07-roadmap.md 的 P0-P5 完成并逐项验收。
