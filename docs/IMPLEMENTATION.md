# 实现与验证记录

Last Reviewed: 2026-10-13

## Delivered

- `scripts/inventory.py`：只读依赖声明盘点，覆盖有限格式，不授予调用资格。
- `scripts/admission.py`：严格白名单格式、绑定与默认拒绝判定。
- `scripts/store.py`、`scripts/common.py`：内容摘要快照、单写者锁、原子 JSON 持久化和审计日志。
- `scripts/runner.py`：固定 JSON 输入／预期、独立比较器所需执行结果、超时与输出限制，不继承密钥环境。
- `scripts/controller.py`、`scripts/intake.py`：上传自动验证、名单维护、调用前检查、撤销及中断恢复。
- `skills/dots-intake/SKILL.md`：项目内接入 Skill，未安装到全局目录。
- `examples/sum-tool`：仅用于演示的无副作用合成工具。

## Verification Evidence

本机 macOS，Python 3.12.13。没有安装候选公共办公依赖，没有连接云端，没有真实工具样本。

| 检查 | 实际结果 |
| --- | --- |
| `python3.12 -m unittest discover -s tests -v` | 29 个测试通过 |
| `python3.12 -m compileall -q scripts examples/sum-tool` | 退出 0 |
| `python3.12 -m py_compile scripts/inventory.py scripts/admission.py` | 退出 0 |
| skill-creator 的 quick_validate.py | Skill is valid |
| 独立 CLI 进程集成验证 | init → upload 自动验证 → 第二份输入调用得到 total=60 → list → revoke → 再调用返回 NOT_ALLOWLISTED |
| 实际生成记录的 Schema 检查 | 本地白名单与核查报告均通过 JSON Schema 校验 |
| 无 local-demo 参数的入口 | 返回 CLOUD_ADAPTER_UNAVAILABLE，无法复用本地通过状态 |

单元测试包含：内容／环境／用例绑定变化、未知入口、失败与缺用例不准入、超时和输出上限、敏感声明不回显、不继承密钥环境、名单和证据损坏、重试先撤销、状态写入中断恢复、输入不执行和输出不覆盖。

CLI 集成验证用临时目录完成，临时产物已清理；可按 docs/USAGE.md 重现。合成测试不代表任意工具、插件或全部依赖兼容。

## Governance Changes

用户授权实现后，将初始治理状态更新为本地实现状态；新增 local-demo 适配器契约和三个有界任务。原云端强制验证与白名单要求保持不变，未因本地实现降低准入标准。

## Remaining Boundaries

1. 尚无 Dots 实际接口，云端执行、原生 Skill／插件加载和授权上下文采集尚未接入。
2. 本地适配器不是恶意代码沙箱，不能防御同 UID 进程改权限或绕过 CLI。只能运行可信合成脚本，不能宣称宿主强制隔离已经完成。
3. 公共运行时与真实业务样本未联合验证；候选依赖文件仍不是锁文件。
4. 真实业务写入测试没有授权范围，当前不支持自动执行它。

真实云端上线前需要取得宿主接口、关闭旁路的控制能力及首个真实工具的输入／预期；届时先补充对应适配器契约，再实施和验收，不引入信任本地测试结果的放行开关。

## 2026-10-13 交付清理

- README 明确当前为演示版；接入、配置和首次验证由交付方负责，接收公司无需操作代码。
- 修正技术用法链接和 Skill 能力描述；说明 POSIX 依赖与尚未验证的 Dots 安装方式。
- 新增 `scripts/build_delivery.py`，按源码清单生成 `dist/dots-intake-source-demo.zip` 和 SHA-256 校验文件，排除 Git 历史、缓存、本机配置及运行状态。保留完整测试和治理文件，便于交付方复现与接手。
- 本机临时目录解压包内副本：29 个测试通过；独立 CLI 验证云端模式返回 CLOUD_ADAPTER_UNAVAILABLE 且不创建状态。压缩包完整性、SHA-256、排除项与 Markdown 相对链接检查通过。
- 这次验证覆盖源码交接与本地行为，未连接 Dots，不代表云端安装成功或真实工具验收通过。
