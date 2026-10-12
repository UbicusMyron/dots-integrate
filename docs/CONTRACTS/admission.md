# 强制准入与白名单契约 v1

Last Reviewed: 2026-10-12

## Purpose

Skill 维护并呈现通过验证的工具列表，受控验证器负责持久化有效白名单，统一调用入口负责强制执行。上传内容及上传方自带报告均不具备授予权限。

## Schema And Binding

白名单 JSON 的机器结构见 [allowlist.schema.json](allowlist.schema.json)。初始内容为 `{"schema_version":1,"revision":0,"entries":[]}`，不是预先信任任何工具。

每个条目只授权一个入口，绑定以下字段：

| Field | Meaning |
| --- | --- |
| tool_id | 注册后的稳定工具标识，不以展示名称区分工具 |
| operation | 实际可调用的入口／插件工具标识；不接受通配符 |
| artifact_digest | 完整不可变工具快照的 SHA-256 摘要 |
| runtime_digest | 云端实际解释器、全依赖锁、系统程序、模型及插件运行版本清单的摘要 |
| context_digest | 非敏感连接上下文的摘要：账户／资源范围、授权范围及其修订标识；不含原始令牌 |
| suite_digest | 测试输入、预期、比较器、入口配置、超时及副作用范围组成的固定用例集合摘要 |
| validation_id | 受控验证器生成的本次验证标识 |
| validated_at | 带时区的验证完成时间 |
| evidence_ref / evidence_digest | 已持久化的云端执行证据位置与内容摘要 |

工具内容摘要覆盖 Skill 指令、脚本、模板、模块、入口和本地附属文件；排除运行输出、缓存与秘密值。使用按相对路径排序的 UTF-8 JSON 文件清单，每项含相对路径、文件内容 SHA-256 和可执行位，再对清单取摘要；JSON 用紧凑分隔符，禁止重复路径、目录逃逸及未解析链接。快照生成后只读；调用与验证使用同一快照，不能检查工作目录后再运行另一个可变路径。

运行时、上下文和用例的摘要清单使用同样的确定性 JSON 编码（键排序、UTF-8、紧凑分隔符），清单结构与实际值由可信采集器保存。它们不是上传方声明。远程插件无法取得可绑定版本或实际连接状态时，不声称已满足版本绑定。

## Minimum Loop And Admission

授予条目必须同时满足：

1. 内容、环境、连接及用例的绑定值可从可信来源取得，上传版本不能在测试期间被替换。
2. 对该入口完成实际云端加载、真实核心依赖调用、输入处理、输出生成和自动结果断言。纯 import、退出码 0、上传方的 `passed=true`、本地测试或全 mock 测试都不足够。
3. 核查报告 `outcome=passed`，且证据能证明当前绑定及测试覆盖；未解决的必要依赖没有未知、缺失或冲突。
4. 证据持久化成功，验证器再次核对当前绑定未变化，然后原子写入白名单；保存失败不放行。

自动生成测试可以作为准备步骤，正式运行前固定输入、预期和比较器；工具不得修改断言后为自身授予资格。无需人工逐条批准已授权的无副作用测试。若缺少可自动判定的业务预期，状态为 blocked，取得预期后继续；不能退化为 Agent 自述“看起来正确”。

只测了预览入口就只开放预览。需要真实业务写入的入口，用已授权测试资源执行并回读；没有可用测试范围时保持禁用。测试资格不改变网关或插件本来的授权规则。

## Invocation Contract

内部判定函数用于下一个有界任务；返回值不是可缓存或可转交的授权令牌：

```python
evaluate_admission(binding: dict, registry: dict | None) -> dict
# binding 的键严格为前六个绑定字段：tool_id、operation、四个 *_digest。
# 允许：{"allowed": True, "code": "ADMITTED", "validation_id": "run-001"}
# 拒绝：{"allowed": False, "code": "NOT_ALLOWLISTED", "validation_id": None}
```

调用器从受控存储读取当前名单并从实际快照／环境／连接／注册用例构造 binding；不能直接接受运营传入的摘要。身份、名单完整性、重复记录和外部权限检查在执行入口完成；该纯函数只判断其输入，不证明来源可信。

执行入口须在启动前完成全部检查，并将执行绑定到已检查的不可变快照。撤销／环境切换与启动受同一控制锁或等效宿主机制约束；已接受启动的任务记录其 validation_id，撤销阻止之后的新调用，不承诺回滚已经发生的业务动作。不得把早先判定结果拿到稍后绕过重新检查。

## Errors And Decision Order

所有拒绝发生在业务入口执行前；返回稳定机器码和脱敏原因。纯函数依以下顺序判定，避免实现自行决定优先级：

| Code | Condition |
| --- | --- |
| INVALID_BINDING | binding 字段缺失、多余、类型不符或摘要格式不符 |
| REGISTRY_UNAVAILABLE | registry 为 null，表示受控读取失败 |
| REGISTRY_INVALID | 名单结构不符、版本不支持或存在重复完整绑定 |
| NOT_ALLOWLISTED | 名单中不存在相同 tool_id 和 operation 的任何条目 |
| BINDING_MISMATCH | 存在该工具入口，但没有六字段全部匹配的条目 |
| ADMITTED | 完整绑定恰好匹配一个有效条目 |

真实调用器还必须拒绝 `UNTRUSTED_REGISTRY`（名单来源／写权限不可信）、`CONTEXT_UNAVAILABLE`（无法取得当前环境或连接）、`PERMISSION_DENIED`（现有业务权限不允许）、`EVIDENCE_INVALID`（证据丢失或摘要不符）。这些宿主边界不由纯函数推测。

## Examples And Validation Rules

- 有效空白名单：上传后还未验证，任何合法 binding 都返回 NOT_ALLOWLISTED。
- 完全匹配条目：返回 ADMITTED；同一名称但改了脚本摘要，返回 BINDING_MISMATCH。
- 插件中 `preview` 已通过，不代表 `publish` 可用；调用 publish 返回 NOT_ALLOWLISTED。
- 上传方拷贝一份合法 JSON：不因满足 Schema 而可信；调用器必须只读自己的受控权威名单。
- 同一完整六字段绑定不允许出现两次；不同不可变版本可并存。条目只表示有效授权，失败、阻塞、撤销等历史不放在 entries 中。
- 授予及撤销递增 revision。消费者不使用缺乏失效机制的名单缓存；v1 每次调用读取受控最新版本。
- token 自动续期但账户、范围和授权修订不变时无须重测；身份、权限或工具版本变化必须重新绑定验证。无法判定变化时拒绝。

## Compatibility And Versioning

schema_version 为 1。字段或状态语义变化须升级契约并更新读写双方；不支持的版本默认拒绝。普通核查报告仍用 v1，不增加自动授予权限的字段。

## Open Questions

- Dots 各类工具入口的版本／连接采集器和权限边界尚未验证；实际宿主适配契约须在该部署任务开始前写明。
- 第一份真实用例、预期及比较器仍缺失；本文定义门槛，不伪造通过条目。
