# Task: 实现默认拒绝的白名单判定

Status: Implemented; verification recorded in docs/IMPLEMENTATION.md
Last Reviewed: 2026-10-12

## Goal

实现 admission 契约中的纯判定函数，以合成数据验证版本绑定和默认拒绝；不伪称已接入云端强制拦截。

## Source Context

- `docs/SPEC.md`：强制最小闭环与白名单要求。
- `docs/ARCH.md`、`docs/RULES.md`：控制边界及可信来源要求。
- `docs/CONTRACTS/admission.md`、`docs/CONTRACTS/allowlist.schema.json`：输入输出、结构及错误顺序。
- `docs/CONTRACTS/identity-access.md`：调用器与验证器的职责。

## Scope

### Touch

- `scripts/admission.py`：纯函数 evaluate_admission，以标准库实现当前 Schema 对应的确定性字段校验、RFC 3339 带时区时间检查和完整绑定去重。
- `tests/test_admission.py`：内联合成白名单和变更用例。

### Do Not Touch

- 不写入真实白名单，不运行工具，不连接云电脑，不安装依赖。
- 不实现上传、哈希采集器、验证执行器、状态持久化、身份隔离或调用器适配。
- 不把测试构造的合法名单视为可信授权证据；真实信任边界属于后续宿主集成任务。

## Interfaces

- Consumes: binding 和 registry，具体六字段及名单结构见 admission 契约；registry 可为 None。
- Produces: `{allowed, code, validation_id}`，严格遵循契约判定顺序。
- Public contracts touched: None；实现已定义的内部纯函数。
- Downstream tasks relying on this: 云端验证器授予、受控名单读写与实际调用前拦截；宿主能力确认后分别切片。

## Acceptance Criteria

1. 空名单、缺名单、格式错误、不支持版本、重复完整绑定全部拒绝，错误顺序符合契约。
2. 只有六字段精确匹配时允许；分别修改内容、环境、连接、测试或入口，都不得复用旧结果。
3. 不接受通配入口、缺证据字段或无时区的时间；同一工具不同不可变版本可独立匹配。
4. 不修改输入、不读取外部文件、不缓存旧决策；删除条目后的下一次判定立即拒绝。

## Verification

- Command: `python3 -m unittest discover -s tests -p 'test_admission.py' -v`
- Expected evidence: 上述正反用例通过，并断言稳定错误码；测试明确它验证的是输入判定，不是云端执行或名单来源可信性。
- Command: `python3 -m py_compile scripts/admission.py`
- Expected evidence: 退出 0，记录所用 Python 版本。
- If not run: 实际验证记录见 docs/IMPLEMENTATION.md；云端验证不在本任务内。

## Governance Drift Check

- SPEC changed? 默认无，函数仅实现准入规则的一层。
- ARCH changed? 默认无，不新增服务或存储。
- CONTRACTS changed? 默认无；若发现字段或判定顺序冲突，先修订契约再实现。
- RULES/AGENTS changed? 默认无，沿用强制准入边界。
- If no durable docs changed, why is that safe? 实现范围已有精确内部接口，真实宿主集成不在本任务内。

## Risks And Handoff Notes

预计 2 个文件、约 150–250 行；不为实现完整 JSON Schema 引擎扩张范围，只校验当前契约。审查者需核对实现与 Schema 同步，尤其 Python bool 不得当作整数版本／revision 接受。后续仍须独立验证控制存储权限、云端最小闭环及所有调用入口均被拦截，才能宣称强制机制完成。
