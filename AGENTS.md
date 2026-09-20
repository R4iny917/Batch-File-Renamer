# 仓库协作指南

## 项目结构与架构

本项目是使用 Python 3.11+ 和 PySide6 开发的 Windows 桌面应用。修改行为前阅读 [README](README.md) 和 [架构说明](docs/architecture.md)，遵循 [开发流程](docs/workflow.md)；涉及视觉或交互时，同时阅读 [UI 规范](docs/ui-guidelines.md)。

- `renamer/core.py`：命名规则、校验、文件快照和预览。
- `renamer/operations.py`、`windows.py`：执行、撤销、恢复与 Windows 文件安全。
- `renamer/workspace.py`：应用状态；业务模块保持独立，不依赖 Qt。
- `renamer/ui/`：窗口、面板、控件、样式、弹窗及后台任务；仅主线程访问控件。
- `renamer/assets/`：应用图标；`tests/`：自动化测试。
- `build.py`、`Batch File Renamer.spec`、`start.cmd`：打包配置与开发启动入口。

## 构建、测试与开发命令

在仓库根目录使用 PowerShell 执行：

```powershell
# 创建环境、安装依赖并启动
py -3 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe -m renamer
# 常规测试与独立的 Windows 原生测试
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
& .\.venv\Scripts\python.exe tests/test_native_ui.py --run
# 安装构建依赖并打包
& .\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
& .\.venv\Scripts\python.exe build.py
```

打包需要 Windows x64。只保留 `dist/latest/`、`dist/previous/` 和最新 ZIP。替换前若程序正在使用，请用户完成必要操作后关闭；不得强制终止会话而丢失撤销记录。

## 编码风格与命名

使用四空格缩进，函数和变量使用 `snake_case`，类使用 `PascalCase`，常量使用 `UPPER_CASE`。遵循相邻代码风格及现有类型标注；目前未配置格式化或静态检查工具。

优先局部修改，避免不必要的抽象和无关重构。删除代码前检查调用、测试、动态入口与打包引用。

## 测试与文件安全

使用 `unittest`，测试文件命名为 `test_*.py`，测试方法为 `test_*`。只使用临时文件，不使用用户数据。目前没有数值化覆盖率门槛；行为变更应补充有意义的回归测试，尤其关注冲突检查、回滚、恢复和撤销。保留扩展名处理及不覆盖文件的保证。

交付前运行相关测试。后台模式测试不能替代 Windows 原生验证。UI 改动先提供可批注的浏览器预览，经用户确认后实施；交付前在常规和小窗口下，将实际程序截图与批准预览对照。

## 提交、拉取请求与协作

始终使用中文交流。较大改动先调查、提出计划，确认后实施；已获得的批准持续有效。

提交记录采用 Conventional Commits，后续使用简洁中文摘要，例如 `fix(ui): 修复文件名选区丢失`。仅在获得授权后提交或推送；排除虚拟环境、二进制产物、压缩包、缓存及 `artifacts/`。

拉取请求说明修改内容、实际验证及风险；UI 改动附必要的对照截图，仅关联真实存在的 Issue。职责或行为变化时同步更新架构及相关文档。
