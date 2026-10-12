# 云端公共运行时 v1

Status: Active
Last Reviewed: 2026-10-12

## Decision And Status

采用 **Linux + 标准 CPython 3.12 + 一个公共 Python 环境 + 常用办公依赖 + 按需扩展**。目标是降低现有办公脚本的接入成本；“兼容性优先”不表示任意旧包都能运行。

本文件确定版本策略与候选依赖，尚未在 Dots 安装或联合验证。候选输入见 [requirements.in](../runtime/requirements.in)；它不是锁文件，不可用于声称环境已可重建或验收通过。

## Platform Baseline

| 项目 | v1 约定 |
| --- | --- |
| 系统 | 沿用 Dots 提供的 64 位 Linux；候选依赖以 glibc 平台为目标，不为此重装操作系统 |
| 架构 | 能选择时优先 x86_64；现有环境若为 aarch64，先核对实际 wheel，不引入模拟层 |
| Python | 标准 CPython 3.12，初始构建候选 3.12.15；保持 GIL 的常规构建，不选预发布版或特殊 ABI |
| Python 更新 | 后续同系列安全补丁经回归后更新；发行版回移修复的构建按供应方修复记录评估，不能只比较版本字符串 |
| 安装位置 | 一个由维护流程管理的公共 venv，与系统 Python 分开；所有工具指向同一个解释器 |
| 运算 | CPU 为默认，不要求 GPU／CUDA |
| 文本与时间 | UTF-8；日志带时区，业务日期按输入明确解释，不依赖机器默认时区 |
| 环境记录 | 保存系统／架构／glibc、Python 完整版本、解释器路径、依赖锁、系统程序和模型版本 |

3.12 是面向已有办公与 OCR 生态的工程选择。官方列出其安全维护到 2028-10；本次核实到 3.12.15 安全发布。3.11 剩余支持期更短；没有真实工具要求时暂不迁到更新的小版本。官方 3.12 后续发布为源码形式，实际二进制来源由云端供应方或可信构建渠道提供，本规范不要求临时现场编译。[Python 支持表](https://devguide.python.org/versions/)、[3.12.15 发布说明](https://www.python.org/downloads/release/python-31215/)

## Core Dependencies

以下范围是待解析的工程约束；构建时选取范围内可用且共同满足依赖的非撤回正式版，再锁定精确版本。范围允许更新，不代表服务运行时可以自动升级。

| 能力 | 候选范围 | 用途与边界 |
| --- | --- | --- |
| 数值 | `numpy>=2.2.6,<3` | 统一 NumPy 2 系列；不混装按 NumPy 1 ABI 构建的旧扩展 |
| 表格数据 | `pandas>=2.3.3,<2.4` | 先保留 2.3 行为，减少旧脚本迁移成本 |
| Excel | `openpyxl>=3.1.5,<3.2` | `.xlsx` 读写；不承诺运行 Excel 公式引擎 |
| Word | `python-docx>=1.2,<1.3` | `.docx` OOXML 读写 |
| PowerPoint | `python-pptx>=1.0.2,<1.1` | `.pptx` OOXML 读写 |
| XML | `lxml>=6,<7` | XML／OOXML 操作 |
| 图片 | `Pillow>=12,<13` | 图片读写与预处理 |
| PDF 基础 | `pypdf>=6,<7` | 拆分、合并、元数据与基础文本操作 |
| PDF 提取 | `pdfplumber>=0.11,<0.12` | 文本／表格提取，扫描件需 OCR |
| PDF 生成 | `reportlab>=4.4,<5` | 生成 PDF，中文字体需显式选择 |
| HTTP | `requests>=2.32.5,<3` | 调用已有网关；不引入第二套 HTTP 客户端作为必装项 |

pandas 3.0 改变字符串类型与 Copy-on-Write 等行为，先用 2.3 是接入现有脚本的取舍，不是永久禁止升级。[官方迁移说明](https://pandas.pydata.org/docs/whatsnew/v3.0.0.html)

NumPy 2 存在 API 与二进制兼容性变化；选择 2 系列是面向当前生态的起点，不承诺兼容 NumPy 1 时代的原生扩展。遇到旧扩展先确认其支持版本或适配工具，不为单个工具静默降级公共环境。[NumPy 迁移指南](https://numpy.org/doc/stable/numpy_2_0_migration_guide.html)

已核对 Python 3.12 可用证据的主要来源包括 [pandas 2.3.3 的 Linux CPython 3.12 wheel](https://pypi.org/project/pandas/2.3.3/)、[NumPy 2.2.6 文件](https://pypi.org/project/numpy/2.2.6/)、[python-docx Python 要求](https://pypi.org/project/python-docx/)、[python-pptx Python 要求](https://pypi.org/project/python-pptx/)、[pdfplumber 测试版本](https://pypi.org/project/pdfplumber/)。这些证据不等于整组依赖已联测。

其他候选包参考维护者页面：[openpyxl](https://pypi.org/project/openpyxl/)、[lxml](https://pypi.org/project/lxml/)、[Pillow](https://pypi.org/project/pillow/)、[pypdf](https://pypi.org/project/pypdf/)、[ReportLab](https://pypi.org/project/reportlab/)、[Requests](https://pypi.org/project/requests/)。以上来源核查日期均为 2026-10-12。

## Optional Capabilities In The Same Environment

这些是同一公共环境的按需扩展，不是每个工具各建一个环境；加入扩展后须重新解析完整依赖集合并回归。

| 需求 | 选择 | 加入条件 |
| --- | --- | --- |
| 轻量 OCR | `pytesseract>=0.3.13,<0.4` + Tesseract 5 系列 | 需要扫描件／图片文字；同时提供 `eng`、`chi_sim`、`chi_tra` 中实际需要的语言数据 |
| 更复杂中文／版面 OCR | PaddleOCR 3 系列 + 相容的 PaddlePaddle 3 CPU 构建 | 真实样本证明需要；精确组合、模型和 CPU 指令能力联测后加入；不预装 `[all]` |
| OpenCV 预处理 | 优先一个 headless OpenCV 发行包 | 实际工具需要时加入；检查 OCR 链传递依赖，不能同时装多个提供 `cv2` 的发行包 |
| PDF 渲染 | Poppler 工具，或已有且经过验证的渲染库 | 需要生成页面图片时加入，不把文本提取当作渲染验证 |
| Office 渲染／旧格式转换 | LibreOffice headless | 实际需要 `.doc/.xls/.ppt` 转换或 Office → PDF 时加入；一般 OOXML 编辑无需它 |
| 字体 | 选定 Noto CJK 字体文件 | 中文文档或 PDF 样例需要时固定具体文件、版本与使用路径，检查缺字和版式 |
| TS／浏览器工具 | 复用云端已有能力 | 首个实际工具出现后记录 Node、浏览器和插件版本，不因此预建第二套平台 |

`pytesseract` 还需要系统 Tesseract 可执行文件；只有 Python 包不够。[安装要求](https://pypi.org/project/pytesseract/)
PaddlePaddle 安装矩阵含 Python 3.12，但模型、PaddleOCR 和整组依赖仍需共同验证。[PaddlePaddle 安装指南](https://www.paddlepaddle.org.cn/documentation/docs/zh/install/index_cn.html)、[PaddleOCR 安装指南](https://www.paddleocr.ai/main/en/version3.x/installation.html)
OpenCV 官方包说明要求在共享命名空间的发行包中只选一种。[OpenCV 包说明](https://pypi.org/project/opencv-python-headless/)

已有工具若依赖 PyMuPDF、其他 OCR 或文档库，先记录并核查原库，不因默认表不同而自动重写或换库。

## Build, Lock And Update Rules

1. 先读取真实云端环境；只在临时构建副本解析候选清单，不在服务中的环境试装。
2. 使用与目标一致的 Python／系统／架构，优先且默认只接受 wheel。缺 wheel 时报告具体包，不自动转为源码编译。
3. 构建时把所有启用扩展与核心依赖一起解析；对元数据冲突给出原因，不用 `--no-deps` 强行安装。
4. 固定直接和间接依赖、哈希、Python 构建来源及系统程序版本；保存可取得的 wheel 或可信制品来源。`requirements.in` 只是输入，`pip freeze` 只是快照，单独任何一个都不是完整发布锁。
5. 样例验证通过后发布一个有版本标识的公共环境。日常工具不执行 `pip install`、升级、降级或用户目录安装来绕过锁。
6. 更新先回归所有已接入工具。保留上一版本用于整体恢复；临时测试副本不作为长期第二环境。
7. 范围上限阻止必要修复时，更新约束并回归，不永久停留在旧系列或静默越过约束。
8. 环境发布版本参与工具白名单绑定。新公共环境切换前重验拟开放工具；新环境不能沿用旧环境名单。恢复旧环境时仍须使用未撤销且完全匹配其内容与连接上下文的验证记录。

固定全依赖与哈希的依据见 [pip 可重复安装说明](https://pip.pypa.io/en/stable/topics/repeatable-installs/)；wheel 选择与干运行参数见 [pip install 文档](https://pip.pypa.io/en/stable/cli/pip_install/)。

## Verification Before Release

运行位置是获授权的临时目标环境副本，`python` 必须解析到拟发布的公共解释器。以下是后续验证要求，本轮没有执行：

```sh
python -m pip install --dry-run --ignore-installed --only-binary=:all: --report resolver-report.json -r runtime/requirements.in
python -m pip check
python -c 'import sys, numpy, pandas, openpyxl, docx, pptx, lxml.etree, PIL, pypdf, pdfplumber, reportlab, requests; print(sys.version); print(sys.executable)'
```

第一条只验证候选解析并写报告；后两条需在候选依赖已安装的副本中运行。解析报告不是锁文件。必要扩展也必须参加同一次解析，不能只检查核心包后声称 OCR 兼容。

除依赖检查外，须保留：中文 `.docx/.pptx/.xlsx` 读写样例，PDF 提取／生成结果，数值／日期对照，以及启用 OCR 后的中文扫描件和预期文本。Office 渲染或 PDF 生成还须查看实际页面；不能只看 import 是否成功。没有真实工具时可用合成样例检查基础环境，但项目验收仍按 SPEC 进行。

## Open Questions

- 尚无 Dots 环境快照，不能确认 CPU 架构、glibc、解释器来源、权限与预装包；不生成虚假的已验证锁文件。
- 尚无真实工具，不能确定要启用哪种 OCR、是否需要渲染及具体模型／字体文件；核心范围与这些扩展的联合解析仍待执行。
