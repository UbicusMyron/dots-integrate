# Dots 工具接入与强制验证

已实现静态依赖盘点、白名单判定，以及**可信合成工具的本地演示闭环**：上传 → 自动验证 → 通过入名单 → 调用前检查 → 撤销／失效后拒绝。

云端模式默认拒绝。当前没有 Dots 的真实执行入口、宿主权限隔离或插件加载适配器；本地通过记录不能授予云端资格。`--local-demo` 不是安全沙箱，只用于你信任且无副作用的合成脚本，不能运行未知来源工具。项目使用 Python 标准库，无须安装公共办公依赖来运行本项目。

## 快速演示

在本项目根目录使用 Python 3.12。下面会创建本地 `.demo-state`，上传示例并自动执行两个用例；重复初始化会拒绝覆盖已有状态。

```sh
python3.12 scripts/intake.py --state .demo-state --local-demo init
python3.12 scripts/intake.py --state .demo-state --local-demo upload --tool examples/sum-tool > .demo-upload.json
python3.12 scripts/intake.py --state .demo-state --local-demo list
```

用另一份输入调用已通过的版本，再撤销：

```sh
DOTS_ARTIFACT="$(python3.12 -c 'import json; print(json.load(open(".demo-upload.json"))["artifact_digest"])')"
python3.12 scripts/intake.py --state .demo-state --local-demo call --artifact "$DOTS_ARTIFACT" --operation sum --input examples/call-input.json
python3.12 scripts/intake.py --state .demo-state --local-demo revoke --artifact "$DOTS_ARTIFACT" --operation sum
python3.12 scripts/intake.py --state .demo-state --local-demo call --artifact "$DOTS_ARTIFACT" --operation sum --input examples/call-input.json
```

第一次调用返回 `{"total":60}`，最后一次返回 NOT_ALLOWLISTED 并退出 2。修复后可用 `validate --artifact "$DOTS_ARTIFACT" --operation sum` 明确重试；重试会先撤销该版本入口的旧资格。更改原工具后重新 upload 会得到新摘要，不继承旧资格。

所有结果标明 `mode: local-demo`。upload／validate 出口 0 表示本地用例全部通过；1 表示保存了失败／阻塞结果；2 表示请求或控制状态错误。不能用 0 声称云端验收通过。

## 静态依赖盘点

```sh
python3.12 scripts/inventory.py --tool examples/sum-tool --output /tmp/dots-inventory-report.json
```

输出文件必须不存在且位于被检查目录之外。仅识别 requirements.txt 的简单声明；示例使用标准库、无该文件，因此报告 DECLARATION_MISSING 和 unverified。它不会执行工具，也不会授予名单资格。

## 接入材料与证据

本地适配器使用 [intake.json 示例](examples/sum-tool/intake.json)：入口接收 JSON stdin，输出 JSON stdout；声明固定输入与预期，由独立比较器精确对比。完整格式与限制见 [本地适配器契约](docs/CONTRACTS/local-demo.md)。

每个入口独立验证。缺用例、缺依赖、版本不符、非零退出、输出不是 JSON、结果不符或超时均不准入。快照内容、当前 Python／包版本、用例或连接上下文变化后，旧绑定无法调用；名单或证据损坏也不会回退直调。

状态目录保存：

- `snapshots/`：按摘要标识的只读工具副本。
- `records/`：每次验证的状态与固定用例。
- `evidence/`：本地输入／预期／实际结果、断言、依赖信息和核查报告，仅用合成数据。
- `allowlist.json`：有效本地条目，工具不能靠自报 passed 入库。
- `events.jsonl`：验证、调用、拒绝和撤销记录，不保存脚本 stderr 或继承环境中的密钥。

本地只读文件不能防御同用户代码主动改权限；真正的宿主隔离仍需在云端实现。不要手工修改名单，也不要将其复制到生产。

## 验证与后续接入

```sh
python3.12 -m unittest discover -s tests -v
python3.12 -m compileall -q scripts examples/sum-tool
```

项目 Skill 入口：[skills/dots-intake/SKILL.md](skills/dots-intake/SKILL.md)，需连同项目脚本和文档使用；尚未安装到全局技能目录。

治理入口：[AGENTS.md](AGENTS.md)。公共环境候选：[docs/RUNTIME.md](docs/RUNTIME.md)。本轮没有安装这些办公包或生成云端依赖锁。

真实上线仍需 Dots 接口、一个真实工具的输入／预期、受控验证身份及关闭直接执行旁路的证据。在取得这些条件前，本项目不提供“相信本地结果”的云端放行开关。
