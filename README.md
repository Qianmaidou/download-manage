# download-manage

Windows 下载文件夹整理工具 — 将杂乱文件按类型自动分类。现代化 GUI 界面，开箱即用。

## 快速开始

### 下载 EXE（推荐）

从 [Releases](https://github.com/Qianmaidou/download-manage/releases) 下载最新 `zip`，解压后双击 `下载文件夹整理工具.exe`。

无需安装 Python 或任何依赖。

### 源码运行

```bash
git clone https://github.com/Qianmaidou/download-manage.git
cd download-manage
pip install customtkinter
python gui.py
```

## 功能

| 功能 | 说明 |
|------|------|
| 自动分类 | 照片、文档、压缩包、安装包、其他 — 按扩展名智能归类 |
| 预览整理 | 扫描下载文件夹，展示每个文件的目标分类 |
| 浏览分类 | 整理后查看各目录内容，支持删除 |
| 回收站删除 | 删除文件移入回收站，可从桌面还原 |
| 撤销整理 | 一键恢复上次整理操作 |
| 自定义路径 | 界面中选择下载文件夹，或恢复自动检测 |
| 智能去重 | SHA256 比对，相同文件自动跳过 |
| 快捷键 | `Ctrl+P` 预览 `Ctrl+O` 整理 `Ctrl+Z` 撤销 `Delete` 删除 |

## 界面

```
┌──────────────────────────────────────────────────────────┐
│  下载文件夹整理工具                          [_][□][X]   │
├────────┬─────────────────────────────────────────────────┤
│  📋    │  下载文件夹: ~\Downloads       [更改] [重置]    │
│  整理   │                                                │
│        │  文件名       类型   目标分类   操作             │
│  📁    │  photo.png    文件   照片      → 照片/          │
│  浏览   │  report.pdf   文件   文档      → 文档/          │
│        │  ...                                            │
│  📝    │                                                │
│  日志   │  [照片:14] [文档:35] [压缩包:14] ... 共73      │
│        │                                                │
│        │  [🔍 预览] [▶ 整理] [🗑 删除] [↩ 撤销]        │
├────────┴─────────────────────────────────────────────────┤
│  就绪                                                    │
└──────────────────────────────────────────────────────────┘
```

## 命令行

```bash
python organize.py              # 整理
python organize.py --dry-run    # 预览
python organize.py --undo       # 撤销
```

## 配置

编辑 `config.json`：

```json
{
  "downloads_path": "auto",
  "categories": {
    "photos":     { "name": "照片",   "extensions": [".png", ".jpg", ".jpeg", ".gif", ".bmp", ".svg", ".webp"] },
    "documents":  { "name": "文档",   "extensions": [".pdf", ".doc", ".docx", ".xlsx", ".pptx", ".txt", ".md", ".srt"] },
    "archives":   { "name": "压缩包", "extensions": [".zip", ".rar", ".7z", ".tar.gz", ".tar", ".gz"], "include_folders": true },
    "installers": { "name": "安装包", "extensions": [".exe", ".msi"] },
    "others":     { "name": "其他",   "extensions": [] }
  },
  "ignored_patterns": ["desktop.ini", "*.crdownload", "*.tmp"]
}
```

| 字段 | 说明 |
|------|------|
| `downloads_path` | `"auto"` 自动检测，或填绝对路径 |
| `include_folders` | `true` 时文件夹归入该分类 |
| `extensions` | 空数组 `[]` = 兜底分类 |

## 项目结构

```
├── gui.py                    # GUI 界面 (CustomTkinter)
├── organize.py               # CLI 命令行
├── config.json               # 分类规则
├── build.bat                 # EXE 构建脚本
└── lib/
    ├── classifier.py         # 文件分类
    ├── config_loader.py      # 配置加载
    ├── file_ops.py           # 文件操作
    ├── history.py            # 操作历史
    └── reporter.py           # 统计报告
```

## 版本

| 版本 | 更新 |
|------|------|
| v3.0.0 | CustomTkinter 现代 UI、回收站删除、全 16pt 字号 |
| v2.1.0 | 侧边栏 + 蓝色主题 + 浏览分类 |
| v1.0.0 | CLI 命令行、五分类整理 |

## License

MIT
