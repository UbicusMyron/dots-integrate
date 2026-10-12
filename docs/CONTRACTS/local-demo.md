# 本地闭环适配器 v1

Last Reviewed: 2026-10-12

## Scope

2026-10-12 用户确认尚无云端入口与真实工具，本轮实现本地演示闭环。所有执行命令必须显式指定 `--local-demo`；未指定时返回 CLOUD_ADAPTER_UNAVAILABLE，不创建云端白名单、不执行工具。本地状态只能用于演示，不构成安全沙箱：只运行可信、无副作用的合成工具。云端插件／纯 Skill 加载适配器未实现。

## CLI

```text
python3 scripts/intake.py --state PATH --local-demo init
python3 scripts/intake.py --state PATH --local-demo upload --tool DIRECTORY
python3 scripts/intake.py --state PATH --local-demo validate --artifact DIGEST --operation NAME
python3 scripts/intake.py --state PATH --local-demo call --artifact DIGEST --operation NAME --input INPUT_JSON
python3 scripts/intake.py --state PATH --local-demo list
python3 scripts/intake.py --state PATH --local-demo revoke --artifact DIGEST --operation NAME
```

upload 自动尝试验证清单中每个入口；缺用例或依赖时保存 blocked，不调用业务入口。validate 用于明确重试，并先撤销同一内容与入口旧资格。call 不触发隐式重测。stdout 为一份 JSON；错误为 stderr 上 `{error:{code,message}}`，退出 2。upload／validate 若生成了失败或阻塞结果则退出 1；正常退出 0。

## Tool Manifest

工具根目录 `intake.json` 是本地适配器的声明。所有键严格校验，不接受任意 shell 命令、路径外跳、符号链接、隐藏配置目录、秘密文件或 URL 下载。

```json
{
  "schema_version": 1,
  "tool_id": "sum-demo",
  "kind": "module",
  "dependencies": [],
  "operations": {
    "sum": {
      "script": "sum.py",
      "timeout_seconds": 10,
      "side_effects": "none",
      "cases": [{"input": {"values": [2, 3]}, "expected": {"total": 5}}]
    }
  }
}
```

kind 可为 module／skill／plugin，但本地执行只支持它们包内显式提供的 Python 脚本入口，不证明整个 Skill／插件运行正常。dependencies 每项严格为 `{distribution:非空包名,version:精确版本}`；实际环境必须安装该精确版本。cases 可为空，此时阻塞；每项严格为 input／expected 两个 JSON 值，独立比较器用规范 JSON 精确比较，不执行上传方的断言代码。timeout_seconds 可省略，默认 300 秒，必须是 1–3600 的整数；side_effects 只能为 none。实际有副作用的脚本不可用于本地演示；此声明不是操作系统隔离。

脚本以同一 Python 解释器启动，用 stdin 接收一个 JSON 值，stdout 输出一个 JSON 值；非零退出、非 JSON、超过 1 MiB 输出、超时均失败。工作目录是独立临时目录，脚本从快照读取；不继承密钥环境变量。限制不能防御恶意同用户代码，因此仅适用于可信演示。

## State And Evidence

本地状态目录包含 mode.json、allowlist.json、snapshots、records、evidence、events.jsonl 及控制锁。mode 必须为 local-demo。使用单进程文件锁串行化上传、验证、调用与撤销；JSON 临时文件写入、fsync 后原子替换。初始化不覆盖已有目录，读取损坏名单不自动重建。

快照排除 .git、__pycache__、*.pyc；对其余符号链接、非普通文件、隐藏路径及 .pem/.key 文件拒绝。普通配置也可能含秘密，运营在上传前仍需检查。演示快照最多 512 个普通文件、合计 16 MiB；超出返回 ARTIFACT_LIMIT。工具摘要遵循 admission 契约。运行时摘要实际采集 Python、平台、解释器文件摘要与已安装发行包版本；本地 context 固定为 local-demo/no-external-connections。用例摘要包含独立比较器版本、标准化入口配置及全部输入预期。

验证记录保存完整 binding、固定用例、状态、尝试编号及证据引用；扩展 workflow v1 的引用记录为自包含本地记录。证据记录结果摘要、断言和依赖检查，核查报告遵循 intake-report v1；不存脚本 stderr 内容。失败撤销条目，崩溃遗留 validating 在下次控制操作时转 blocked。名单与 passed 记录或证据不一致时拒绝并撤销，禁止恢复历史资格。

无生产允许模式、无自动部署、无远端凭据或身份伪造开关。展示结果始终包含 mode=local-demo。

## Errors

核心错误沿用 admission 契约。适配器增加 CLOUD_ADAPTER_UNAVAILABLE、INVALID_MANIFEST、UNSAFE_PATH、ARTIFACT_CHANGED、DEPENDENCY_MISSING、DEPENDENCY_CONFLICT、MISSING_TEST_CASE、TEST_TIMEOUT、OUTPUT_LIMIT、INVALID_OUTPUT、EXECUTION_FAILED、RESULT_MISMATCH、STATE_INVALID、STATE_EXISTS。

## Verification Boundary

本地合成用例验证流程、拒绝语义和恢复行为，不验证云端宿主权限隔离、远程插件、真实工具正确性或公共依赖环境兼容性。
