# 对齐默认输出安全与印章唯一表示

状态：completed
负责人：Codex
创建日期：2026-07-23
最后更新：2026-07-23 +08:00

## 目标与用户价值

修复审查中确认的两项高优先级差异：CLI 未指定输出路径时安全写入项目 `output/`，不再默认
写入输入文件旁边；存在 PaddleX 结构化印章识别结果时，每枚物理印章只输出一个带稳定 ID 和
正文引用的 `SealDetail`，不再同时保留普通版面 `Seal` 块。

本任务不修改远端请求协议、印章坐标算法、用户样本或现有烟测结果。

## 当前事实与约束

- `src/pdf_parser/cli.py` 当前使用 `input_pdf.with_name(...)`，与 `AGENTS.md` 的默认
  `output/` 约束冲突。
- `normalization/paddlex.py` 会先把 `parsing_res_list[label=seal]` 转为普通 `Seal`，
  再从 `seal_res_list` 追加结构化 `SealDetail`。
- `validate_result.py` 要求所有 `type=Seal` 的元素都有 `seal_id`，真实烟测结果已证明重复的
  普通 `Seal` 会被拒绝。
- 工作区没有 Git 提交，所有文件均为未跟踪状态；只修改本计划列出的文件，不触碰
  `resources/` 和既有 `output/`。

## 实施阶段

- [x] 阶段 1：修改默认输出路径，并用 CLI 测试证明不会覆盖输入旁的同名结果。
- [x] 阶段 2：在存在结构化印章结果时过滤普通版面 Seal，并补回归测试。
- [x] 阶段 3：同步 README，运行定向测试和完整 harness 检查。

## 具体改动

- `src/pdf_parser/cli.py`：默认输出改为 `output/<stem>_result.json`，同步帮助文本。
- `tests/test_cli.py`：模拟解析服务，验证默认输出位置和输入旁文件不被覆盖。
- `src/pdf_parser/normalization/paddlex.py`：结构化印章存在时不创建重复普通 Seal。
- `tests/test_normalization.py`：构造同时包含版面 Seal 和 `seal_res_list` 的响应并断言唯一表示。
- `README.md`：更新默认输出说明。

## 验证与验收

```powershell
uv run pytest tests/test_cli.py tests/test_normalization.py --basetemp .pytest-tmp-focused
& .\.harness\scripts\check.ps1
```

验收要求：定向测试通过；默认输出位于 `output/`；输入旁同名文件保持不变；含原始 Seal 块和
结构化结果的页面只产生一个 `SealDetail`；完整离线门槛通过。若完整门槛仍仅因既有
`output/smoke` 诊断脚本格式失败，单独报告该已知非本任务问题，不修改诊断产物。

## 进度记录

- 2026-07-23 — 已复核 AGENTS、harness 工作流、CLI、归一化实现和现有测试；开始实施。
- 2026-07-23 — 两项实现与回归测试完成；定向测试 7 项通过。
- 2026-07-23 — `src/` 和 `tests/` 格式、Lint 通过，完整离线测试 18 项通过。
- 2026-07-23 — 完整 `check.ps1` 仍被既有 `output/smoke/.../run_comparison.py` 格式问题
  阻断；该问题属于先前审查的中优先级生成目录隔离项，不在本任务范围内。
- 2026-07-23 — 默认 PaddleX 健康检查在沙箱内外均连接失败，因此未运行真实 PDF 烟测。

## 意外发现

内置补丁工具在更新既有文件时遇到 Windows 沙箱刷新错误；改用补丁文件加 `git apply` 完成
同等的文本补丁，新增文件仍由补丁工具创建。

## 决策记录

- 决策：默认输出以调用命令时的当前工作目录为基准，写入 `output/`。
  理由：这与 AGENTS 的项目级安全目录约定和现有命令示例一致，并避免写入用户样本目录。
  日期：2026-07-23
- 决策：只在存在有效结构化 `seal_res_list` 时跳过普通版面 Seal。
  理由：消除已确认的重复表示，同时保留远端没有结构化印章结果时现有的标签映射兼容行为。
  日期：2026-07-23

## 恢复与回滚

中断后从未完成的阶段继续。回滚时只撤销本计划列出的源码、测试和 README 修改；不删除或
覆盖 `resources/`、`output/` 和用户已有文件。

## 结果总结

CLI 默认输出已改为当前工作目录的 `output/<stem>_result.json`，回归测试确认不会覆盖输入
旁边的同名用户文件。归一化在存在结构化 `seal_res_list` 时会过滤普通版面 Seal，回归测试
确认每枚印章只产生一个带 `seal_id` 的 `SealDetail` 和一条正文引用。README、AGENTS 测试
目录和 harness 架构测试映射已同步。远端请求与坐标算法未改变；默认 PaddleX 服务不可用，
真实烟测未运行。
