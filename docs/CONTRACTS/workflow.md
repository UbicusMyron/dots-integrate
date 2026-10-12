# 云端验证状态机 v1

Last Reviewed: 2026-10-12

## Purpose And Record

每个工具入口及完整绑定拥有独立生命周期，验证器为唯一写者。验证工作流版本为 1。记录结构如下；此示例为合成状态，不是运行证据：

```json
{
  "workflow_version": 1,
  "validation_id": "demo-run-001",
  "tool_id": "demo-tool",
  "operation": "preview",
  "state": "pending",
  "attempt": 1,
  "binding_ref": "controlled/bindings/demo.json",
  "suite_ref": "controlled/suites/demo.json",
  "evidence_ref": null,
  "reason_code": null,
  "updated_at": "2026-10-12T22:00:00+08:00"
}
```

字段均必填；state 只能取下表状态，attempt 为正整数，两个 *_ref 为非空字符串，evidence_ref 和 reason_code 可以为 null，updated_at 为带时区时间。绑定内容遵循 admission 契约。记录存在不等于已授予白名单资格。

## States And Transitions

| From | Trigger | To | Guard / side effect |
| --- | --- | --- | --- |
| 无 | 接收新上传内容／新入口 | pending | 记录不可变版本，业务调用仍拒绝 |
| pending | 输入、预期、环境或必要授权缺失 | blocked | 保存缺口，不执行业务写入 |
| pending | 准备条件齐全 | validating | 固定绑定与用例，先持久化状态，再运行测试 |
| validating | 全部断言通过 | passed | 保存可信证据，再原子写名单，最后标记 passed；写失败转 blocked |
| validating | 结果不符、执行错误或超时 | failed | 保存证据，确认该绑定不在有效名单 |
| validating | 环境不可用、取消或进程中断 | blocked | 不授予；无法确认外部写入结果时记录结果未知 |
| failed / blocked | 原因已处理，明确请求重试 | pending | attempt 加一，新 validation_id；不自动重放有副作用操作 |
| passed | 同绑定请求重新验证 | pending | 先撤销该条目，再运行；旧的成功回调不能重新授予 |
| passed | 撤销或已知依赖／权限失效 | revoked | 移除名单并保存原因，拒绝新调用 |
| revoked | 问题解决后请求重新验证 | pending | 创建新的验证尝试，不直接改回 passed |

未列出的流转全部拒绝。新的 artifact/runtime/context/suite 摘要是新绑定，从 pending 开始；不会覆盖其他仍有效的不可变版本。

## Steps And Minimum Case

每个用例需固定：入口、输入引用、预期引用、自动比较器引用、超时和副作用范围。它们共同进入 suite_digest。默认单用例超时 300 秒；确有需要时在用例中明确延长并重新取摘要，不能无限等待。

1. 核查依赖、云端实际环境和连接。
2. 验证器使用目标云电脑的正式加载／调用适配器运行指定入口，待验证工具仅获得测试范围资源。
3. 记录输出和必要的外部回读，用固定比较器判定结果。
4. 保留脱敏日志、输入／预期／实际输出及全部绑定证据。
5. 重新确认绑定和本次尝试仍有效后写白名单。相同 validation_id 的重复回调只能幂等返回，不重复增加条目。

试运行例外入口只允许执行固定用例，不能接受任意业务请求。工具自报成功不能代替独立比较器。

## Failure, Cancellation And Recovery

- v1 不自动重试测试执行；一次失败有一条明确结果，避免重复业务写入。
- 重启发现 validating 但无可确认的活跃执行时转 blocked，不假定成功。启动恢复必须完成控制记录一致性检查，才能开放业务入口。
- 若崩溃发生在证据落盘后、名单写入前，仍未授予。若名单已写而最终状态未落盘，恢复时撤销不一致条目并复核，不重放测试。
- 取消应停止本次执行及其受控子任务；无法确认已经停止时保持 blocked，不授予。外部已发生写入不声称自动回滚，先查实际结果。
- 同绑定撤销及尝试编号作为迟到结果的有效性条件；旧进程／回调不得使已撤销绑定复活。
- 权限、证据、工作流记录或名单损坏时拒绝并给出原因，不回退直调。

## Errors

`{"error":{"code":"INVALID_TRANSITION","message":"脱敏原因"}}`。
稳定错误包括 INVALID_TRANSITION、MISSING_TEST_CASE、TEST_TIMEOUT、RESULT_MISMATCH、CANCELLED、EXECUTION_INTERRUPTED、STALE_VALIDATION、PERSISTENCE_FAILED、SIDE_EFFECT_OUTCOME_UNKNOWN。

## Versioning

每次验证固定 workflow_version。升级时不接纳旧流程的迟到授予；未完成尝试标记 blocked，按新流程重新验证。有效条目是否需要失效由变更影响决定，不以文件版本变化静默扩权。

## Open Questions

- 真实工具的样本、比较器及副作用范围缺失，因而云端验证执行尚不能开始。
