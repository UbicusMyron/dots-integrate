# Task: 生成只读静态依赖盘点报告

Status: Implemented; verification recorded in docs/IMPLEMENTATION.md
Last Reviewed: 2026-10-12

## Goal

用一个标准库脚本把根 requirements.txt 的简单声明转为带证据的未验证报告，给核查 Skill 提供第一个确定性步骤。

## Source Context

- `docs/SPEC.md`：依赖显式化、未验证状态与非目标。
- `docs/ARCH.md`：Skill／脚本边界及公共环境约束。
- `docs/RULES.md`：只读核查、脱敏与验证规则。
- `docs/CONTRACTS/static-inventory.md`：输入、解析范围、退出码。
- `docs/CONTRACTS/intake-report.md` 与 `docs/CONTRACTS/intake-report.schema.json`：输出格式。

## Scope

### Touch

- `scripts/inventory.py`：命令行与静态盘点。
- `tests/test_inventory.py`：使用临时目录的行为测试与内联合成样本。
- `skills/dots-intake/SKILL.md`：说明本阶段仅静态盘点，并引导人工补充其他依赖；不声称全流程完成。

### Do Not Touch

- 不连接 Dots、Mac Mini、Drive 或业务系统，不安装依赖，不修改原工具或共享环境。
- 不实现完整 requirements 解析器、插件探测、自动适配、上传发布或业务试运行。
- 不创建真实工具验收通过记录，不增加后台服务或外部依赖。

### Public Contracts

- Allowed to change: None；按现有内部契约实现。若发现契约缺陷，先明确提出并在授权范围同步修订。
- Forbidden to change: 外部业务 API、认证、运行环境及业务数据。

## Interfaces

- Consumes: CLI 参数及工具根 requirements.txt，见 static-inventory 契约。
- Produces: intake-report v1 JSON；stderr 错误封套与退出码。
- Public contracts touched: None；实现已定义的内部文件／CLI 接口。
- Downstream tasks relying on this: Skill 补全隐含依赖、强制云端验证与白名单准入；下一可独立开发切片见 `docs/TASKS/002-admission-decision.md`。静态盘点结果不得直接用于准入。

## Acceptance Criteria

1. 支持契约中的简单声明，保留行号证据和重复行，所有依赖均为未验证。
2. 缺声明、空声明、超出范围的行均不会被误认为工具不依赖任何东西；报告说明覆盖范围。
3. 不执行工具、不联网、不安装包、不修改输入；含凭据的 URL／索引行不进入报告或 stderr 原文。
4. 拒绝覆盖已有输出，处理非法目录、符号链接、编码与 I/O 失败，错误码符合契约。
5. Skill 明确脚本局限、后续补充步骤和真实验收门槛；本任务通过不宣称产品通过。

## Verification

- Command: `python3 -m unittest discover -s tests -p 'test_inventory.py' -v`
- Expected evidence: 临时目录测试通过，覆盖正常声明、未知行、缺声明、空文件、编码失败、非法路径、输出不覆盖、凭据不泄漏；断言 schema_version、必需字段、状态和错误封套。测试设置可执行哨兵文件，验证扫描没有执行它。
- Command: `python3 -m py_compile scripts/inventory.py`
- Expected evidence: 退出 0；语法兼容执行测试所记录的 Python 版本。
- If not run: 实际验证记录见 docs/IMPLEMENTATION.md；云端验证不在本任务内。

## Governance Drift Check

- SPEC changed? 仅静态盘点切片，不改变产品验收；发现范围不一致时同步修订。
- ARCH changed? 不引入新依赖或边界；新增依赖须说明必要性。
- CONTRACTS changed? 默认无；接口不符时修复实现，不暗改格式。
- RULES/AGENTS changed? 仅出现可重复约束时更新；不复制现有规则到 Skill。
- If no durable docs changed, why is that safe? 本任务只实现已经写明的内部接口，不声明新的产品能力。

## Risks

预期 3 个文件、约 200–300 行、无公共 API／业务 schema 变更；若超出，先按可独立验收的行为拆分。有限解析必须明确显示，不能用“扫描完成”掩盖依赖发现未完成。

## Handoff Notes

- Reviewer should check: 未验证语义、实际解析覆盖、敏感行处理、输入无副作用、已有输出不变。
- Human should decide: 提供首个真实工具及输入／预期；这一事实缺口只阻塞后续真实验收。
