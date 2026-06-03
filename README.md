# download-manage

Windows 下载文件夹自动整理工具 — 将散乱的文件按类型分类到子文件夹，长期可复用。

## 功能

- **GUI 可视化界面**: `python gui.py` 启动窗口程序
- **定时自动整理**: GUI 中设置间隔，后台自动运行
- **预览整理效果**: 可视化查看文件分类和目标目录
- **撤销支持**: 一键撤销最近一次整理
- **智能去重**: 哈希比对，相同文件自动去重
- **冲突处理**: 同名不同内容文件自动加序号
- **文件夹归类**: 下载的文件夹（解压内容）归入「压缩包」

## 安装

```bash
git clone https://github.com/Qianmaidou/download-manage.git
cd download-manage
```

仅需要 Python 3.7+，无第三方依赖。

## 使用

### GUI 界面（推荐）

```bash
python gui.py
```

功能说明：
- **🔍 预览** — 扫描下载文件夹，显示文件分类和目标目录
- **▶ 立即整理** — 执行整理，带进度反馈
- **↩ 撤销** — 撤销最近一次整理
- **⏹ 停止** — 停止当前操作或定时器
- **启用自动整理** — 设置间隔（15分钟～24小时），到时间自动执行
- **快捷键**: `Ctrl+P` 预览, `Ctrl+O` 整理, `Ctrl+Z` 撤销

### 命令行

```bash
# 预览将要执行的操作
python organize.py --dry-run

# 执行整理
python organize.py

# 详细输出每个文件的操作
python organize.py --verbose

# 撤销最近一次整理
python organize.py --undo

# 静默模式（适合定时任务）
python organize.py --quiet
```

## 配置

编辑 `config.json` 可自定义分类规则：

```json
{
  "downloads_path": "auto",
  "categories": {
    "photos": {
      "name": "照片",
      "extensions": [".png", ".jpg", ".jpeg", ".gif", ...]
    },
    "documents": {
      "name": "文档",
      "extensions": [".pdf", ".docx", ".pptx", ...]
    },
    "archives": {
      "name": "压缩包",
      "extensions": [".zip", ".rar", ".7z", ...],
      "include_folders": true
    },
    "installers": {
      "name": "安装包",
      "extensions": [".exe", ".msi", ...]
    },
    "others": {
      "name": "其他",
      "extensions": []
    }
  },
  "ignored_patterns": [
    "desktop.ini",
    "*.crdownload",
    "*.tmp"
  ]
}
```

- `downloads_path`: `"auto"` 自动使用 `~/Downloads`，或指定绝对路径
- `include_folders`: `true` 表示文件夹归入该分类
- `ignored_patterns`: fnmatch 模式，匹配的文件会被忽略

## 定时运行（Windows Task Scheduler）

1. 打开「任务计划程序」
2. 创建基本任务 → 触发器「每天」
3. 操作 → 启动程序：
   - 程序: `python`
   - 参数: `C:\Users\y2639\Desktop\下载文件夹整理\organize.py --quiet`
   - 起始于: `C:\Users\y2639\Desktop\下载文件夹整理\`

## 项目结构

```
.
├── gui.py                    # GUI 可视化界面
├── organize.py               # CLI 命令行入口
├── config.json               # 分类规则配置
├── README.md                 # 使用说明
├── DEVLOG.md                 # 开发日志
│
└── lib/
    ├── __init__.py
    ├── classifier.py         # 文件/文件夹 → 分类
    ├── config_loader.py      # 配置加载校验
    ├── file_ops.py           # 安全移动、冲突解决、去重
    ├── history.py            # 操作历史（撤销用）
    └── reporter.py           # 输出和统计
```

## License

MIT
