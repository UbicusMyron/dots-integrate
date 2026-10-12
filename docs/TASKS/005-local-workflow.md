# Task: 连接验证、白名单及受控调用闭环

Status: Implemented for local-demo; verification in docs/IMPLEMENTATION.md
Last Reviewed: 2026-10-12

## Goal

连接验证、白名单及受控调用闭环；只实现用户已接受的本地演示闭环。

## Source Context

- docs/SPEC.md、docs/ARCH.md、docs/RULES.md。
- docs/CONTRACTS/local-demo.md、docs/CONTRACTS/admission.md、docs/CONTRACTS/workflow.md。

## Scope

### Touch

scripts/controller.py、scripts/intake.py、tests/test_workflow.py、examples/sum-tool、README.md。

### Do Not Touch

真实云端、生产名单、业务数据、凭据、公共运行时安装。

## Interfaces

- Consumes: local-demo 契约的清单、输入和受控状态。
- Produces: 该切片负责的本地状态／结构化结果。
- Public contracts touched: None；本地内部接口见 local-demo 契约。
- Downstream tasks relying on this: 后续宿主适配与真实云端验收。

## Acceptance Criteria

1. 自动验证、失败拒绝、证据绑定、撤销与中断恢复有实际正反向验证。
2. 本地证据不得授予云端调用资格；默认云端路径拒绝。
3. 合成演示不宣称真实工具或身份隔离验收通过。

## Verification

- Command: `python3.12 -m unittest discover -s tests -v`
- Expected evidence: 对应模块及集成的正反向测试通过。

## Governance Drift Check

本地适配器接口已写入 local-demo.md；实现中发现差异同步修订，不修改强制云端准入原则。

## Size Justification

预计每个切片 2–5 个生产文件；流程切片可能超过 300 行，因为授予与撤销的一致性需一起审查。存储、执行器已拆出，不能为压行数省略拒绝与恢复检查。
