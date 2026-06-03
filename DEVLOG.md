# 开发日志

## 第 1 步：项目初始化 + Git 仓库搭建

**时间**: 2026-06-03

**完成内容**:
- 初始化 Git 仓库 `git init`
- 创建 `.gitignore`：忽略 `__pycache__/`、`*.pyc`、IDE 配置、虚拟环境、`history.json`
- 关联远程仓库：`https://github.com/Qianmaidou/download-manage.git`
- 创建项目目录结构：`lib/`
- 创建 `DEVLOG.md` 开发日志文件

**Git 仓库信息**:
- 本地路径：`c:\Users\y2639\Desktop\下载文件夹整理\`
- 远程仓库：`https://github.com/Qianmaidou/download-manage.git`

---

## 第 2 步：config.json + 配置加载模块

**时间**: 2026-06-03

**完成内容**:
- 编写 `config.json`：
  - 5 个分类：照片、文档、压缩包、安装包、其他
  - 48 个扩展名映射（含复合扩展名如 `.tar.gz`）
  - 文件夹归类到「压缩包」（`include_folders: true`）
  - 忽略模式：`desktop.ini`、`*.crdownload`、`*.tmp` 等
  - 下载路径默认 `auto` → `~/Downloads`
- 实现 `lib/config_loader.py`：
  - `load_config()` — 加载并校验 JSON 配置
  - `build_extension_map()` — 构建扩展名→分类查找表（复合扩展名优先，按长度降序）
  - `get_downloads_path()` — 解析下载文件夹路径
  - `get_folder_category()` — 获取文件夹应归入的分类
  - `get_ignored_patterns()` — 获取忽略模式列表
  - `ConfigError` 异常类
- 实现 `lib/__init__.py` — 包初始化文件

**验证结果**:
- 配置加载正常，扩展名映射 48 条，文件夹归入 archives

---

## 第 3 步：分类器模块

**时间**: 2026-06-03

**完成内容**:
- 实现 `lib/classifier.py`：
  - `classify()` — 传入路径 → 返回分类 key
  - 复合扩展名优先匹配（`.tar.gz` 在 `.gz` 之前检查）
  - 无扩展名文件 → `others`
  - 文件夹 → 读取配置中的 `include_folders` 分类
  - 忽略模式匹配（使用 `fnmatch`）
  - `get_category_name()` — 分类 key → 中文名称

**验证结果**:
- 用真实下载文件夹 76 项测试：文档 35、压缩包 14（含 6 个文件夹）、照片 14、其他 5、安装包 5、忽略 3
- 分类结果完全正确

---

## 第 4 步：文件操作 + 历史记录模块

**时间**: 2026-06-03

**完成内容**:
- 实现 `lib/file_ops.py`：
  - `hash_file()` — SHA256 哈希（>100MB 采样优化）
  - `resolve_destination()` — 目标路径解析，冲突时哈希比对
  - `safe_move()` — 安全移动文件，自动去重/序号重命名
  - `move_folder()` — 移动整个文件夹（含冲突处理）
  - `ensure_dir()` — 确保目标目录存在
  - 序号冲突检测：`report.pdf` 冲突 → `report (1).pdf`，`report (1).pdf` 再冲突 → `report (1) (2).pdf`
- 实现 `lib/history.py`：
  - `OperationRecord` — 单次操作记录（时间、移动列表、去重删除列表）
  - `HistoryManager` — JSON 文件读写、追加、弹出、清空
  - 用于支持 `--undo` 撤销功能

**验证结果**:
- 正常移动、去重删除、序号重命名、文件夹移动均正确
- 历史记录保存/加载/弹出均正常

---

## 第 5 步：报告模块 + 主入口 + README

**时间**: 2026-06-03

**完成内容**:
- 实现 `lib/reporter.py`：
  - `Report` 类 — 分类统计（文件数、文件夹数、去重数、跳过数、错误数）
  - `print_dry_run()` — 预览模式输出
  - `print_verbose_move()` — 逐文件详细日志
- 实现 `organize.py` — 主入口：
  - argparse 命令行参数：`--dry-run` `--undo` `--verbose` `--quiet`
  - 完整流程编排：加载配置 → 扫描 → 分类 → 移动 → 记录 → 报告
  - Windows 终端 UTF-8 编码修复
- 实现 `README.md`：使用说明、配置指南、定时任务设置
- **修复**: dry-run 模式意外创建目录的 bug

**验证结果**:
- `--dry-run` 正确预览 73 项整理计划（不创建任何文件）
- 分类统计：照片 14、文档 35、压缩包 14、安装包 5、其他 5、忽略 3
- 中文输出正常（UTF-8 编码修复）

---

## 第 6 步：真实环境测试验证

**时间**: 2026-06-03

**完成内容**:
- 首次实际整理：73 项成功分类（照片 14、文档 35、压缩包 14、安装包 5、其他 5、忽略 3）
- 撤销测试：73 项全部恢复，空分类目录自动清理
- **修复 BUG**：dry-run 模式下不慎创建分类目录 → 移除 `ensure_dir` 调用
- **修复 BUG**：幂等性问题 — 再次运行时分类目录被误当作内容移入「压缩包」→ 添加分类目录名过滤
- **修复 BUG**：`Report.total_files` 中 `"skipped"` 条目缺少 `"files"` 键导致 `KeyError` → 改用 `.get("files", 0)`
- **修复 BUG**：撤销后空分类目录未被清理 → 重写 `_cleanup_empty_dirs`，传入下载根目录和分类名集合
- 端到端验证：整理 → 撤销 → 空目录清理，全部通过

**验证结果**:
- `python organize.py --dry-run` → 预览正确，无副作用
- `python organize.py` → 整理 73 项正确
- `python organize.py`（再次）→ 幂等，不重复整理
- `python organize.py --undo` → 撤销 73 项，空目录自动清理

---

## 第 7 步：最终检查 + 打 tag v1.0.0

**时间**: 2026-06-03

**完成内容**:
- 最终代码审查：7 个 Python 文件、1 个配置文件、README、DEVLOG
- 确认 `.gitignore` 正确排除 `history.json`（运行时文件）
- Git 历史清晰：7 次提交，每步对应一个 commit
- 打 tag `v1.0.0` 并推送到 GitHub

**发布信息**:
- 仓库：`https://github.com/Qianmaidou/download-manage.git`
- Tag：`v1.0.0`
- 总提交数：7 次
- 总代码行数：~550 行 Python + 配置 + 文档

**功能清单**:
| 功能 | 状态 |
|------|------|
| 五分类自动整理（照片/文档/压缩包/安装包/其他） | ✅ |
| 文件夹归类到「压缩包」 | ✅ |
| 复合扩展名处理（.tar.gz） | ✅ |
| 预览模式 `--dry-run` | ✅ |
| 撤销操作 `--undo` | ✅ |
| 哈希去重 | ✅ |
| 同名冲突序号处理 | ✅ |
| 幂等性（多次运行安全） | ✅ |
| 忽略系统文件/未完成下载 | ✅ |
| 操作历史记录 | ✅ |
| 用户可编辑配置文件 | ✅ |
| Windows 终端中文支持 | ✅ |

---

## GUI 可视化窗口开发 (v1.1.0)

**时间**: 2026-06-03

**新增文件**:
- `gui.py` — Tkinter GUI 入口（~700 行）

**完成内容**:

### 窗口框架
- `OrganizeGUI` 主窗口类，920×660 默认大小
- Grid 布局：信息栏 → 按钮栏 → Notebook(预览+日志) → 自动设置 → 状态栏
- 窗口居中显示，关闭协议（进行中操作提示确认）

### 信息栏
- 下载文件夹路径显示
- 状态指示器：● 绿色=就绪 / ● 黄色=运行中 / ● 红色=错误
- 上次整理时间（从 history.json 读取）

### 预览功能
- 扫描下载文件夹，调用 `lib.classifier.classify()` 分类
- `ttk.Treeview` 4 列表格：文件名 | 类型 | 目标分类 | 操作
- 底部统计摘要栏（动态生成，按分类显示计數）
- 过滤分类目录自身（幂等性）

### 立即整理
- 确认对话框 → 后台线程执行（`threading.Thread`）
- 进度回主线程更新状态栏和日志
- `--stop` 支持中途停止
- `Report` 统计 + `OperationRecord` 历史记录

### 撤销功能
- 读取最后一条历史记录，确认对话框
- 后台线程逆向移动文件
- 完成后清理空分类目录
- 刷新预览 + 更新统计

### 自动整理定时器
- `tkinter.after()` 调度 + `threading.Thread` 执行
- Checkbutton 开关 + Combobox 间隔选择（15分～24小时）
- 倒计时显示（每秒刷新）
- 执行完成后自动调度下一次

### 异常处理 + 快捷键
- 配置文件错误 → messagebox + 退出
- 下载文件夹不存在 → 禁用按钮
- 按钮互斥（运行中禁用操作按钮，停止按钮启用）
- 快捷键：`Ctrl+P` 预览, `Ctrl+O` 整理, `Ctrl+Z` 撤销`
- 线程安全：所有 UI 更新通过 `root.after(0, callback)` 回主线程

**设计原则**:
- GUI 和 CLI 是两个平行入口，共享 `lib/` 模块
- 零新增依赖（Tkinter 是 Python 标准库）
- CLI 代码零改动

---

## v1.1.1 — 选中删除功能

**时间**: 2026-06-03

**新增功能**:
- Treeview 改为多选模式（`selectmode="extended"`）
- [🗑 删除选中] 按钮 — 选中后批量删除
- 右键菜单 — 右键文件行弹出删除/全选菜单
- `Ctrl+A` 全选, `Delete` 键删除
- 删除确认对话框（显示文件列表，文件夹特别警告）
- 删除后自动刷新预览和统计

---

## v1.2.0 — EXE 打包支持

**时间**: 2026-06-03

**完成内容**:
- 新增 `lib/utils.py` — `get_app_dir()` 统一路径解析（支持开发/PyInstaller 双模式）
- 修复 `lib/config_loader.py` — `DEFAULT_CONFIG_PATH` 使用 `get_app_dir()`
- 修复 `organize.py` — `sys.path` 和 `history_path` 支持 frozen 模式
- 修复 `gui.py` — 同上
- 新增 `build.bat` — 一键构建 EXE（PyInstaller --onefile --windowed）
- 更新 `.gitignore` — 排除 `*.spec`

**构建方法**:
1. 双击 `build.bat`
2. 输出: `dist/下载文件夹整理工具.exe`
3. 将 exe 和 config.json 放在同一目录即可运行

---

## v2.0.0 — UI 全面现代化

**时间**: 2026-06-03

**重大改动 — gui.py 完全重写**:

### UI 架构
- **侧边栏导航** 替代 Notebook 选项卡 — 深蓝底色 + 图标按钮
- **蓝色主题** (#2563EB) — ttk.Style 全局覆盖，朴素干净
- **三页面**: 待整理 / 浏览分类 / 操作日志

### 新增功能
- **自定义下载路径**: 「待整理」页顶部 [更改...] 按钮，调用系统文件夹选择器；[重置] 恢复自动检测
- **浏览分类页面**: 左侧分类列表（含文件计数）→ 右侧文件 Treeview（名称/大小/日期），可直接删除
- 整理完成后自动刷新浏览分类列表

### 移除
- 定时自动整理（程序关闭即失效，改为建议用 Windows 任务计划）
- 停止按钮（功能合并到状态栏）

### 保留
- 所有 lib/ 模块不变
- CLI (organize.py) 不变
- 快捷键: Ctrl+P/Ctrl+O/Ctrl+Z/Ctrl+A/Delete
