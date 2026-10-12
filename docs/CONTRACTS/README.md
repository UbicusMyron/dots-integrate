# CONTRACTS

Last Reviewed: 2026-10-12

## Contract Index

| Contract | File | Owner | Consumers | Status |
| --- | --- | --- | --- | --- |
| 核查报告 | [intake-report.md](intake-report.md)、[JSON Schema](intake-report.schema.json) | 核查工具维护者 | Skill、检查脚本、报告阅读者 | 内部 v1 |
| 静态盘点命令 | [static-inventory.md](static-inventory.md) | 检查脚本维护者 | 核查 Skill、操作人 | 已实现，只读静态盘点 |
| 强制准入与白名单 | [admission.md](admission.md)、[JSON Schema](allowlist.schema.json) | 自动验证器 | 统一调用入口、核查 Skill | 内部 v1，本地演示实现；云端待接入 |
| 验证状态机 | [workflow.md](workflow.md) | 自动验证器 | 运营、核查 Skill | 内部 v1，本地演示实现；云端待接入 |
| 控制权限边界 | [identity-access.md](identity-access.md) | 宿主与准入模块 | 验证器、调用器 | 策略已定，宿主映射待核实 |

本地执行适配器与 CLI 见 [local-demo.md](local-demo.md)。本地通过记录不授予云端资格。

本目录定义本项目实际生产的文件和命令。尚未取得的业务网关、插件及 Drive API 不在这里虚构。接口变化同步更新契约、测试和受影响任务。

## Open Questions

- 真实工具和环境出现后，需要补充具体能力探测、试运行入口及预期结果的契约；不阻塞只读静态盘点。
