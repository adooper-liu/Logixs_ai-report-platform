# 运行时契约

状态：P0 基础策略契约已实现；完整连接器、schema、规则、模型、指标、pipeline、publication 契约尚待对应阶段实施。

`arp_contracts` 随根 Python 包安装。项目策略 JSON Schema v1 是本模块唯一编辑源，包内资源读取，无远程 $ref；严格禁止未知字段与 P0 AI 启用/原始样本外发。指纹来自确定性 JSON 序列化，校验不执行任何 AI 代码或 SQL。

- `arp_contracts/schemas/project-policy.v1.json`：运行时项目基础策略。
- `arp_contracts/policy.py`：校验、默认策略与 SHA256 指纹。
- 根 `contracts/control-api.v1.yaml`：已实现基础 API 的 OpenAPI 契约。
- 根 `contracts/ai-recommendation.schema.json`：原有设计期最小建议契约，不代表 AI 已实现。

实际验收与后续范围见根 project.json 和 docs/10-p0-implementation.md。配置版本只新增不原地编辑，不建立双向随意改写的生成物。
