# 核查报告 v1

Last Reviewed: 2026-10-12

## Purpose

统一脚本与 Skill 的核查结果，供 A、B 和后续 Agent 使用。所有结论只覆盖报告声明的工具来源和检查范围；这是内部文件接口，不是业务数据模型。

## Schema

机器可检查的结构见 [intake-report.schema.json](intake-report.schema.json)。UTF-8 JSON，禁止重复键。`schema_version` 固定为 `1`。

- `source_ref`：可定位所检查工具版本或目录的引用；静态目录路径不等于已锁定版本。
- `environment_ref`：被实际检查的目标环境快照引用；未接触目标环境为 `null`。
- `coverage`：本次实际阅读或执行的范围。不能写成“全部依赖”而没有依据。
- `dependencies`：`python / plugin / gateway / account / file / command / implicit` 七类；有需求、状态及证据。
- `issues`：机器码、脱敏说明与可执行的下一步；空数组仅表示没有已记录问题。
- `trial`：输入、预期、实际结果引用与执行证据；`not_run / blocked / failed / passed`。
- `outcome`：`unverified / blocked / passed`，表示本次接入核查结论，不代表项目整体验收或 B 已独立复跑。
- 本报告不能单独授权调用，即使 `outcome=passed`。自动验证器还须按 [admission.md](admission.md) 校验云端证据、内容与环境绑定并写入受控白名单；报告 v1 格式保持不变。

## Examples

有效静态报告；`demo` 是合成示例，不是实际试点：

```json
{
  "schema_version": 1,
  "source_ref": "fixtures/demo",
  "environment_ref": null,
  "coverage": ["requirements.txt: simple declarations only"],
  "dependencies": [
    {"kind": "python", "name": "samplelib", "requirement": "samplelib==1.0", "status": "unverified", "evidence": ["requirements.txt:1"]}
  ],
  "issues": [],
  "trial": {"status": "not_run", "input_ref": null, "expected_ref": null, "result_ref": null, "evidence": []},
  "outcome": "unverified"
}
```

无效示例：把以上报告的 `outcome` 改成 `passed`，同时保留 `trial.status=not_run`。即使包全部已安装，也不能通过接入核查。

## Validation Rules

1. `satisfied` 必须有实际验证证据；源码中的声明只能支持 `unverified`。
2. 缺少声明不代表无依赖；动态导入、外部插件及操作条件必须由后续步骤补充。
3. `passed` 要求目标环境非空、所有已识别依赖为 `satisfied`、`issues` 为空、试运行通过。它只对已记录覆盖范围有效。
4. 试运行 `passed` 必须引用输入、预期、实际结果，并提供执行与比较证据；依赖未知时即使样例偶然成功，总结仍为 `unverified`。
5. 发现确定阻断运行的缺失／冲突，或试运行失败／受阻，`outcome=blocked`；其余未完成验证为 `unverified`。
6. 空证据不得用“Agent 判断通过”补足。证据引用指向可复查内容，不嵌入敏感业务数据。
7. `name` 是逻辑名称，不存认证 URL；敏感命令参数与日志先脱敏。

## Errors

报告中的问题使用 `{ "code": "UPPER_SNAKE_CASE", "message": "脱敏原因", "next_step": "下一步" }`。

| Code | Meaning | Next step |
| --- | --- | --- |
| DECLARATION_MISSING | 没找到本次支持的依赖声明 | Skill 检查其他声明、代码与说明 |
| UNSUPPORTED_DECLARATION | 声明格式超出本次扫描范围 | 记录文件行号并人工核查，不执行或展开 |
| ENVIRONMENT_UNAVAILABLE | 无法检查指定目标环境 | 恢复访问后验证，保留未知状态 |
| CAPABILITY_UNAVAILABLE | 实测缺少必需能力或权限 | 补齐对应能力或连接后复测 |
| TRIAL_MISMATCH | 实际结果与预期不符 | 保存差异，调整工具或确认业务预期 |

未成功读取输入或写出报告的 CLI 错误见 static-inventory 契约；不能伪造完整报告来掩盖 I/O 失败。

## Compatibility And Versioning

新增可选字段须先更新 Schema 与消费者；删除、改名、必填字段变更或改变状态含义需要递增版本。代码枚举新增也需审查消费者兼容性。首期不建设自动迁移服务。

## Open Questions

- 试运行的实际比较规则取决于首个工具；当前没有通过报告的真实样例。
