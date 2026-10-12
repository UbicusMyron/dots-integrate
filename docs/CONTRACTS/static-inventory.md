# 静态依赖盘点 CLI v1

Last Reviewed: 2026-10-12

## Purpose

首个开发切片从根目录 requirements.txt 提取有限、明确的声明，生成未验证报告。它不完成整个产品的依赖发现或云端试运行。

## Interface And Schema

```text
python3 scripts/inventory.py --tool TOOL_DIRECTORY --output NEW_REPORT_JSON
```

两项参数均必填。输入目录必须存在；输出父目录必须存在，目标必须尚不存在且在工具目录外。输入工具目录和所读取 requirements.txt 不得是符号链接；不递归读取其他文件。输出是 intake-report.schema.json 定义的 JSON。

只支持空行、整行 `#` 注释，以及符合下式的完整声明行（去掉行首尾空白后）：

```text
[A-Za-z0-9][A-Za-z0-9._-]*(?:\s*(?:===|==|!=|~=|<=|>=|<|>)\s*[A-Za-z0-9.*+!_-]+)?
```

名称保留原声明拼写；`requirement` 保留去掉首尾空白的整行，证据用 `requirements.txt:行号`。保留重复声明，不静默合并或计算版本兼容性。
额外依赖组、多个版本条件、环境标记、行内注释、续行、URL、路径、`-r`、`--index-url` 等均不解释、不展开、不执行，仅记录 UNSUPPORTED_DECLARATION 与行号，不输出原文。

## Output Semantics

- `source_ref`：输入工具目录的绝对路径；`environment_ref=null`。
- `coverage` 必须说明只读了根 requirements.txt 的简单声明，未读代码／其他清单／插件／账户／目标环境。
- 依赖的 `kind=python`、`status=unverified`；`trial.status=not_run`，三个结果引用为 null，证据为空。
- 无声明文件时生成 DECLARATION_MISSING；文件存在且为空时说明其为空，不认定无依赖。
- 不支持的行记录问题并继续读取可支持的行；`outcome` 始终为 `unverified`。
- 报告写入成功才退出 0；0 只表示盘点报告生成成功，不表示接入通过。

## Examples

成功：根 requirements.txt 有 `samplelib==1.0`，生成 intake-report.md 中同等结构的未验证报告。
缺声明：仍生成报告，dependencies 为空，issues 包含 DECLARATION_MISSING，退出 0。
失败：输出文件已存在时退出 2，原文件字节不变，不覆盖。

## Errors

错误统一写 stderr，单行 JSON：`{"error":{"code":"OUTPUT_EXISTS","message":"Output already exists"}}`；不输出原始声明、令牌或堆栈。失败不留下成功报告，stdout 为空。

| Code | Exit | Condition |
| --- | --- | --- |
| INVALID_ARGUMENT | 2 | 参数缺失、未知参数或无效输入目录 |
| UNSAFE_PATH | 2 | 被读取输入为符号链接，或输出位于工具目录内 |
| OUTPUT_EXISTS | 2 | 输出目标已经存在，包括符号链接 |
| READ_FAILED | 3 | 读取失败或非 UTF-8 |
| WRITE_FAILED | 3 | 输出目录不存在、无写权限或写入失败 |

默认不改输入文件、不安装包、不联网、不导入或执行工具代码。无覆盖写入必须在实际创建文件时保证，不能只提前检查存在性。

## Compatibility And Versioning

本接口是内部 v1。扩展可解析格式时更新覆盖范围和测试；禁止把退出 0 的含义改为工具接入成功。自动执行或安装是新的行为范围，不能作为解析器增强混入。

## Open Questions

- 后续支持 pyproject.toml、其他锁文件及代码隐含依赖的优先级，由真实工具确定；当前未承诺全格式解析。
