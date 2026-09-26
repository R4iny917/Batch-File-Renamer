# 项目架构

这是保持现有行为的结构重构：继续使用 Python、PySide6 和 QTableWidget，不改变命名顺序、文件安全算法、撤销边界及界面样式。

## 模块与职责

```text
renamer/
├── __main__.py         模块及打包入口
├── app.py              QApplication、字体、翻译和窗口装配
├── workspace.py        文件、规则、预览及操作结果的统一状态
├── core.py             纯命名规则、名称校验、文件快照及预览
├── operations.py       改名会话、执行、撤销、回滚、恢复
├── recovery_store.py   本地 JSON 检查点、版本校验与原子保存
├── windows.py          Windows 文件句柄锁定和禁止覆盖的改名
├── ui/
│   ├── main_window.py   组合界面、连接事件、协调任务及关闭
│   ├── rules_panel.py   规则输入、重置、编号联动、命名示例
│   ├── preview_panel.py 表格及绘制、当前行、文件名选区、复制
│   ├── controls.py      步进器、开关、折叠、滚动渐隐、只读选区
│   ├── dialogs.py       确认、错误详情、弹窗样式和安全默认按钮
│   ├── theme.py         全局样式、资源路径、线形图标
│   ├── runtime.py       Windows 字体引擎、标题栏、屏幕适配
│   └── tasks.py         后台 Worker 及异常到 Result 的转换
└── assets/app.svg      应用图标
```

`build.py` 负责构建及发布目录轮换；`.spec` 声明打包入口、资源、图标与无控制台模式；`start.cmd` 保留开发环境双击启动入口。三者继续保留，各自职责不变。

## 依赖与状态归属

- `app → ui.main_window → workspace → core / operations → windows`，底层业务模块不依赖 Qt。
- `Workspace` 持有文件列表、当前 `Rules`、预览 `Entry`、`RenameSession` 和最近的 `Result`。
- `RulesPanel` 持有输入控件，以 `rules_changed(Rules)` 提交用户修改；`set_rules()` 静默同步状态，避免重复刷新。
- `PreviewPanel` 保存不可变预览条目的显示快照，只管理显示与选择；不修改文件、不持有改名会话。
- 面板通过事件交互：`find_requested(str)` 由主窗口连接到规则面板，`example_changed(str)` 更新左侧示例。面板不访问彼此的控件。
- 主窗口持有忙碌状态和 Worker，负责禁用界面、确认操作及关闭检查。只有主线程访问控件。

## 数据流

1. 添加、移除或清空文件，或修改规则。
2. Workspace 计算一次预览，主窗口将结果交给预览面板并更新状态栏。
3. 用户确认执行后，复制本批次的预览列表并交给后台 Worker。
4. Worker 只调用 RenameSession，线程结束后主线程读取 Result。
5. Workspace 根据实际 `moves` 更新可见文件路径，包括部分失败和部分恢复；仅成功执行且确实有改动时重置规则。
6. RenameSession 在每次移动前后原子保存检查点；启动时读取记录并以 Snapshot 核对位置，不自动移动文件。
7. 主窗口静默同步规则控件、渲染预览并显示操作结果。存在中断操作时先询问用户；稍后处理会保留记录并暂停新改名。

清空或移除列表不清除撤销历史；撤销仍覆盖已移除的文件。最近一次成功批次和活动操作保存在 `%LOCALAPPDATA%/Batch File Renamer/recovery.json`。

## 必须保留的实现约束

- Windows 的 `windows:fontengine=freetype` 在 QApplication 创建之前配置，保留现有环境覆盖能力。创建窗口前显式加载系统微软雅黑常规与粗体，由 `configure_fonts()` 统一设置应用字体。
- FilenameEdit 在原生失焦事件后恢复文字选区；普通 offscreen 测试不能代替原生验证。
- 确认框使用具体操作文字，默认按钮和 Escape 均为取消；错误详情使用统一浅色样式。
- 编号起点允许 0、位数 1–8；最后一个扩展名及其大小写不变。
- 文件操作保留预检、句柄锁定、不覆盖、逆序回滚和未完成恢复阻止新批次等约束。
- RecoveryStore 不依赖 Qt，使用版本化 JSON、同目录临时文件、flush/fsync 和原子替换。记录包含本地路径与快照，不包含文件内容；损坏或版本未知时保留记录并失败关闭。
- 启动核验只读取文件并比较快照；只有用户确认后才通过 `check_move()` 和 `rename_locked()` 恢复。身份不匹配或位置不明时不自动改动文件；排除冲突后重新启动以再次核验。
- 构建子进程使用受控 PATH，避免其他软件的 DLL 被错误打包。
- 发布时轮换 `latest`、`previous` 内部内容，不重命名这两个根目录；成功后仅保留最新 ZIP。

## 验证

普通测试：

```powershell
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
& .\.venv\Scripts\python.exe -m compileall -q renamer tests
```

Windows 原生测试必须在独立进程、可用桌面环境中运行：

```powershell
& .\.venv\Scripts\python.exe tests/test_native_ui.py --run
```

普通测试发现原生测试时会跳过，避免共用 QApplication 的 offscreen 平台污染结果。原生测试只使用临时文件和自己创建的窗口，覆盖真实失焦、输入光标、小窗口滚动、编号切换、确认默认按钮和详情展开。

构建后验证 EXE 能从项目目录之外启动，图标与中文界面正常；用临时文件完成一次预览、改名、撤销。保留 `previous` 供回退。EXE、ZIP、测试截图和迁移脚本不加入 Git。

本次迁移的基线为 `5476b80`。定位回归时先比较对应职责模块，保留当前未提交工作后再回退，避免直接清空工作区。
