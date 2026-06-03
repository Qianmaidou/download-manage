# 开发日志

## v1.0.0 — CLI 命令行工具 (2026-06-03)

项目启动，目标是打造一个可长期复用的下载文件夹整理工具，用 Git 管理项目代码。

### 项目初始化
- `git init`，关联 GitHub 仓库 `Qianmaidou/download-manage`
- 创建 `.gitignore`、项目目录结构 `lib/`
- 首个 commit 推送

### 核心模块开发
- **config.json**: 五分类规则（照片/文档/压缩包/安装包/其他），48 个扩展名映射，复合扩展名支持（`.tar.gz`）
- **lib/config_loader.py**: 配置加载校验、扩展名查找表构建、下载路径解析
- **lib/classifier.py**: 文件/文件夹到分类的映射，复合扩展名优先匹配，`fnmatch` 忽略模式
- **lib/file_ops.py**: `safe_move()` 安全移动、SHA256 哈希去重、同名冲突序号 `(1)(2)`、>100MB 采样优化
- **lib/history.py**: `OperationRecord` + `HistoryManager`，JSON 操作日志，用于撤销
- **lib/reporter.py**: 统计报告 + dry-run 预览输出

### CLI 入口
- `organize.py` — argparse 参数：`--dry-run` `--undo` `--verbose` `--quiet`
- 流程：加载配置 → 扫描 → 分类 → 移动 → 记录 → 报告
- Windows 终端 UTF-8 编码修复

### 测试修复
- 真实下载文件夹 73 项整理测试通过
- **Bug**: dry-run 模式 `ensure_dir` 意外创建目录 → 移除
- **Bug**: 幂等性 — 分类目录被误当作内容移入「压缩包」→ 添加分类目录名过滤
- **Bug**: `Report.total_files` KeyError → `.get("files", 0)`
- **Bug**: 撤销后空分类目录未清理 → 重写 `_cleanup_empty_dirs`

### 发布
- 7 次提交，tag `v1.0.0`
- 功能：五分类整理 / 预览 / 撤销 / 去重 / 幂等

---

## v1.1.0 — GUI 可视化窗口 (2026-06-03)

Tkinter GUI 初版，与 CLI 平行入口，共享 `lib/` 模块。

### 功能
- 预览 / 整理 / 撤销 GUI 操作
- 后台线程执行（`threading.Thread`）+ 进度回主线程
- 操作日志 Tab（彩色标签）
- 定时自动整理（`tkinter.after()` 调度）
- 快捷键 `Ctrl+P/O/Z`

---

## v1.1.1 — 选中删除功能 (2026-06-03)

- Treeview 多选模式（`Ctrl/Shift` + 点击）
- 删除按钮 + 右键菜单 + `Delete` 键
- 删除确认对话框（文件列表 + 文件夹警告）
- 删除后自动刷新预览

---

## v1.2.0 — EXE 打包 + 路径自动检测 (2026-06-03)

### EXE 打包
- 新增 `lib/utils.py` — `get_app_dir()` 兼容开发/PyInstaller 双模式 (`sys.frozen`)
- 修复 `config_loader.py` / `organize.py` / `gui.py` 的 `__file__` 引用
- `build.bat` 一键构建脚本（PyInstaller `--onefile --windowed`）

### 下载路径自动检测
- Windows: `USERPROFILE` → `HOMEPATH` → `HOMEDRIVE` → `Path.home()`
- macOS/Linux: `Path.home() / "Downloads"`

---

## v2.0.0 — UI 全面现代化尝试 (2026-06-03)

第一次尝试用原生 Tkinter 实现现代 UI（侧边栏 + 蓝色主题）。

### 改动
- **gui.py 完全重写**: 侧边栏导航（Canvas 手绘）替代 Notebook 选项卡
- 三页面：待整理 / 浏览分类 / 操作日志
- 蓝色主题 (#2563EB)，自定义 ttk.Style
- 浏览分类页面：左侧分类列表 + 右侧文件 Treeview
- 自定义下载路径（GUI 内选择）

### 教训
- `place(relwidth=1)` 在父容器零尺寸时失效 → 应统一用 `grid`
- `rowconfigure` 权重配错行 → 页面高度为 0
- `_switch_page` 在 `_pages` 创建前调用 → 初始化顺序错误
- `is_folder` (PreviewItem 属性) vs `is_dir()` (Path 方法) 混用
- `--windowed` 模式异常静默吞掉 → 必须保留 `report_callback_exception`
- 定时整理程序关闭即失效 → 移除

### Bug 修复历程
- 布局权重修复、`_switch_page` 顺序修复
- 全局异常捕获 + 按钮回调提示
- 删除 `is_folder` → `is_dir()`
- 浏览页切页时自动刷新分类列表

---

## v2.1.0 — Tkinter 稳定版 (2026-06-03)

Bug 修复后的成熟版本，发布正式 Release。

---

## v3.0.0 — CustomTkinter 现代 UI (2026-06-03)

全面重写为 CustomTkinter，吸取 v2.0 全部教训。

### 技术选型
- **CustomTkinter 5.2.2**: 圆角按钮、CTkFrame 卡片、CTkTextbox、CTkProgressBar
- 全浅色主题（白底灰边蓝点缀），侧边栏同为浅色
- 全局 `grid` 布局，严格初始化顺序（数据 → UI → 切换）

### v2.0 教训落实
- `grid(sticky="nsew")` 替代 `place()`
- `_load_config()` → `_build_sidebar()` → `_build_pages()` → `_switch_page(0)`
- `report_callback_exception` 从一开始设置
- 所有路径方法统一 `.is_dir()`

### UI 迭代
- 全局字号逐步放大：11pt → 13pt → 15pt → 最终统一 16pt
- Treeview 行高: 28 → 34 → 50
- Listbox 字号跟随增大
- 日志 Consolas: 10pt → 14pt → 16pt
- 移除 DM logo、状态指示灯、上次整理时间
- 窗口居中：`update_idletasks()` + `winfo_width/height`

### 功能完善
- 回收站删除（`SHFileOperationW` + `FOF_ALLOWUNDO`，可还原）
- 删除后列表立即刷新（保留选中状态）
- 浏览页切页自动加载分类列表

### 发布
- Release `v3.0.0`，EXE 14MB，含 `config.json`
- 项目文件夹清理：删除 `build/dist/release/__pycache__/*.spec/*.zip`

---

## 当前文件结构

```
下载文件夹整理/
├── gui.py              # GUI 入口 (CustomTkinter)
├── organize.py         # CLI 入口
├── config.json         # 分类规则（用户可编辑）
├── build.bat           # EXE 构建脚本
├── README.md           # 项目说明
├── DEVLOG.md           # 本文件
└── lib/
    ├── __init__.py
    ├── classifier.py       # 文件 → 分类映射
    ├── config_loader.py    # 配置加载 + 下载路径检测
    ├── file_ops.py         # 安全移动 / 去重 / 序号
    ├── history.py          # 操作记录（撤销用）
    ├── reporter.py         # 统计报告
    └── utils.py            # 路径工具 (dev/exe 兼容)
```
