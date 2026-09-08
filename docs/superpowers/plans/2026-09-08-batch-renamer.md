# 文件批量改名工具 Implementation Plan

> For agentic workers: use superpowers:executing-plans to implement this plan task-by-task in this session. 用户已批准开始，不再次请求方案确认；不提交 Git。

**Goal:** 交付可在 Windows 本地运行的中文批量改名工具。

**Architecture:** core 生成不可变预览条目，operations 管理不覆盖文件的批次与恢复记录，app 展示和执行确认。文件操作在 Qt 工作线程运行，期间禁用输入，完成后更新列表。

**Tech Stack:** Python >=3.11、PySide6、unittest；项目内 .venv。

**Spec:** ../specs/2026-09-08-batch-renamer-design.md

## Global Constraints

- 仅 Windows 文件改名；不覆盖、不递归、不跨目录移动。
- 中文界面；保留最后一个扩展名；编号按表格顺序。
- 符号链接、目录、占用目标、仅大小写变化均拒绝。
- 会话内一次撤销，失败恢复记录优先处理，不因失败丢失历史。
- 测试只操作临时目录；实际用户文件必须经界面确认才改名。

## 1. 运行环境与纯规则

Files: requirements.txt, .gitignore, renamer/__init__.py, renamer/core.py, tests/test_core.py

Interfaces: Rules(find, replace, prefix, suffix, numbering, start, digits); Snapshot.capture(path); Entry(source, target, snapshot, error); build_preview(paths, rules) -> list[Entry]。

- [x] 创建 .venv，安装 PySide6；验证 import。
- [x] 用 unittest 测试中文、复合扩展名、编号顺序、重复目标、禁用名、目录、源不存在。
- [x] 运行 `.venv/Scripts/python.exe -m unittest discover -s tests -p test_core.py -v`，确认因功能缺失失败。
- [x] 实现规则转换、目录名称缓存、快照及预览。预览只读，错误留在对应行。
- [x] 重跑同一命令，确认通过。

验证实例：`照片.JPG` + prefix=`旅行_` + suffix=`_精选` + numbering=True => `旅行_照片_精选_001.JPG`；`archive.tar.gz` 查找 tar 替换 zip => `archive.zip.gz`；a.txt 和 b.txt 都变为 x.txt 时整批拒绝。

## 2. 执行、恢复与撤销

Files: renamer/operations.py, tests/test_operations.py

Interfaces: RenameSession.execute(entries), undo(), recover() -> Result; Result(ok, message, errors, moves); Move(source, target, snapshot); session.history 和 session.pending 保存逆向恢复所需的实际已完成移动。

- [x] 临时文件写入不同字节内容，测试改名后内容不变、撤销后回原位。
- [x] 注入边界故障：第二次系统改名失败、恢复目标被占用、源被替换、目标在预检后出现。
- [x] 运行 operations 测试，确认缺失行为失败。
- [x] 使用 Windows SetFileInformationByHandle 的不覆盖语义，逐次检查快照、目标占用及同目录；失败逆序回滚，保留无法恢复的条目。
- [x] 撤销预检全批次；失败回滚到撤销前；恢复成功后保留此前历史。
- [x] 重跑测试，验证每个失败场景的路径和文件内容。

## 3. 中文桌面界面

Files: renamer/app.py, renamer/__main__.py, tests/test_app.py

Interfaces: MainWindow.add_paths(paths), refresh_preview(); execute/undo/recover 按钮启动 Worker，完成信号携带 Result 后应用实际 moves。

- [x] Qt offscreen 集成测试：添加、去重、输入前缀、冲突禁用、取消不改名、确认执行、撤销、恢复。
- [x] 运行界面测试，确认缺失行为失败。
- [x] 创建单窗口：规则表单、对照表格、状态与操作栏、空状态。预览列使用深青色，错误文字红色并配文字状态；使用 Microsoft YaHei UI 和 Consolas 数字字体。
- [x] 操作期间禁用输入和关闭；结果显示逐项错误和恢复按钮。恢复未完成时阻止新批次。
- [x] 重跑集成测试；保存实际 Qt 渲染截图到 artifacts/preview.png 并检查布局。

## 4. 启动与交付

Files: start.cmd, README.md

- [x] 提供双击启动器：切换到项目目录，用本地 .venv 启动；缺少依赖时给出 README 位置，异常保留终端输出。
- [x] 写安装、启动、规则、撤销边界和测试命令。说明虚拟环境依赖当前基础 Python，迁移时需重建。
- [x] 运行 `.venv/Scripts/python.exe -m unittest discover -s tests -v` 和编译检查。
- [x] 启动可见窗口供用户试用；报告自动化验证范围，不把渲染检查声称为人工操作验收。

## 实际结果

2026-09-08 完成。当前项目 .venv 使用 Codex 附带的 Python 3.12.14，安装 PySide6-Essentials 6.11.2；默认下载缓慢，经权限流程使用清华镜像完成安装。没有修改系统 PATH，也没有创建 Git 提交。

- 全套 34 项自动化测试通过，包含 6 项 Qt 后台界面集成测试。
- 文件操作 14 项测试曾连续运行 20 轮，共 280 次通过；随后新增撤销恢复测试，最终文件操作测试为 15 项。
- compileall 与 pip check 通过。
- 独立审查发现源文件身份检查和改名之间的替换竞态，已增加 renamer/windows.py，通过锁定句柄核对身份并执行不覆盖改名；复核通过。
- Win32 改名结构必须为 UTF-16 文件名分配空终止符，长度字段排除终止符；已通过重复执行验证。
- Windows 原生窗口启动成功，字体库读取到 383 个字体，实际窗口截图保存至 artifacts/preview.png 并完成布局检查；示例文件均来自临时目录，未改动用户文件。
- 原生检查窗口已自动关闭。用户可以双击 start.cmd 自行试用；尚未声称完成用户手动桌面交互验收。
