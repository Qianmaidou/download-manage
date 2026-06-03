# download-manage

Windows 下载文件夹整理工具 — 将杂乱文件按类型自动分类。提供现代化 GUI 和命令行两种使用方式。

## 快速开始

### 方式一：下载 EXE（无需 Python）

从 [Releases](https://github.com/Qianmaidou/download-manage/releases) 下载最新版 `download-manage-v2.x.x.zip`，解压后双击 `下载文件夹整理工具.exe` 即可。

### 方式二：源码运行

```bash
git clone https://github.com/Qianmaidou/download-manage.git
cd download-manage
python gui.py
```

仅需 Python 3.7+，零第三方依赖。

---

## GUI 界面

```
┌────────┬──────────────────────────────────────────────────┐
│  DM    │  ┌─ 下载文件夹 ───────────────────────────┐     │
│        │  │ C:\Users\xxx\Downloads    [更改] [重置] │     │
│ ▋📋    │  └───────────────────────────────────────┘     │
│  待整理 │                                                │
│        │  文件名         类型   目标分类   操作           │
│  📁    │  cjson.png      文件   照片      → 照片/        │
│  浏览   │  report.pdf     文件   文档      → 文档/        │
│        │  ...                                           │
│  📝    │  [照片:14] [文档:35] [压缩包:14] ...  共73项    │
│  日志   │                                                │
│        │  [🔍 预览] [▶ 立即整理] [🗑 删除] [↩ 撤销]    │
├────────┴──────────────────────────────────────────────────┤
│  ● 就绪    上次整理: 2026-06-03 17:00                    │
└─────────────────────────────────────────────────────────┘
```

### 三个页面

| 页面 | 功能 |
|------|------|
| **📋 待整理** | 预览下载文件夹，按分类展示每个文件的去向；一键整理或选择性删除 |
| **📁 浏览** | 整理后查看各分类目录内容，支持浏览和删除已整理的文件 |
| **📝 日志** | 彩色操作日志，记录每次整理、删除、撤销的详细过程 |

### 操作方式

| 操作 | 方法 |
|------|------|
| 预览 | 点击 [🔍 预览] 或 `Ctrl+P` |
| 整理 | 点击 [▶ 立即整理] 或 `Ctrl+O` |
| 撤销 | 点击 [↩ 撤销] 或 `Ctrl+Z` |
| 删除 | 选中文件后按 `Delete` 或右键 → 删除 |
| 全选 | `Ctrl+A` |
| 更改路径 | 点击 [更改...] 选择文件夹，[重置] 恢复自动检测 |

### 自定义下载路径

GUI 顶部显示当前下载文件夹路径。点击 [更改...] 可浏览选择任意文件夹，点击 [重置] 恢复自动检测。无需手动编辑配置文件。

---

## CLI 命令行

```bash
python organize.py              # 执行整理
python organize.py --dry-run    # 预览（不修改文件）
python organize.py --undo       # 撤销最近一次整理
python organize.py --verbose    # 逐文件详细输出
python organize.py --quiet      # 静默模式
```

CLI 与 GUI 共享同一套配置和历史记录，可混用。

---

## 配置

编辑 `config.json` 自定义分类规则：

```json
{
  "downloads_path": "auto",
  "categories": {
    "photos":    { "name": "照片",   "extensions": [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".webp", ".ico"] },
    "documents": { "name": "文档",   "extensions": [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".md", ".csv", ".rtf", ".srt"] },
    "archives":  { "name": "压缩包", "extensions": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".tgz", ".cab", ".iso", ".tar.gz", ".tar.bz2"], "include_folders": true },
    "installers":{"name": "安装包", "extensions": [".exe", ".msi", ".dmg", ".pkg", ".deb", ".rpm", ".apk"] },
    "others":    { "name": "其他",   "extensions": [] }
  },
  "ignored_patterns": ["desktop.ini", "*.crdownload", "*.tmp", "*.part"]
}
```

| 字段 | 说明 |
|------|------|
| `downloads_path` | `"auto"` 自动检测；或填写绝对路径 |
| `include_folders` | `true` 时文件夹归入该分类 |
| `ignored_patterns` | fnmatch 通配符，匹配的文件跳过 |
| `extensions` | 空数组 `[]` 表示作为兜底分类（其他） |

---

## 项目结构

```
.
├── gui.py                    # GUI 可视化界面
├── organize.py               # CLI 命令行入口
├── config.json               # 分类规则（用户可编辑）
├── README.md
├── DEVLOG.md                 # 开发日志
├── build.bat                 # PyInstaller 构建脚本
│
└── lib/
    ├── classifier.py         # 文件/文件夹 → 分类
    ├── config_loader.py      # 配置加载校验 + 下载路径检测
    ├── file_ops.py           # 安全移动、SHA256 去重、序号冲突
    ├── history.py            # 操作历史记录（撤销用）
    ├── reporter.py           # 统计报告
    └── utils.py              # 路径工具（开发/EXE 双模式）
```

## 版本历史

| 版本 | 主要更新 |
|------|---------|
| v2.0.0 | 侧边栏导航、蓝色主题、浏览分类、自定义路径 |
| v1.2.0 | EXE 打包、下载路径自动检测 |
| v1.1.0 | GUI 可视化窗口、定时整理 |
| v1.0.0 | CLI 命令行、五分类整理、撤销、去重 |

## License

MIT
