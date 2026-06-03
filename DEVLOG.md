# 开发日志

## v3.0.0 — 正式版 (2026-06-03)

**CustomTkinter 现代 UI + 回收站删除 + 全功能稳定**

### 技术栈
- GUI: CustomTkinter 5.2 (全浅色主题 + 圆角组件)
- 构建: PyInstaller (单文件 EXE, 14MB)
- 依赖: Python 3.7+, customtkinter

### 功能
- 侧边栏导航（整理 / 浏览 / 日志）
- 自动分类：照片、文档、压缩包、安装包、其他
- 预览整理效果 + 统计摘要
- 浏览已整理分类目录，支持删除
- 回收站删除（可恢复）
- 撤销整理操作
- 自定义下载路径 + 自动检测
- SHA256 去重 + 同名冲突序号
- 快捷键: Ctrl+P/O/Z/A/Delete
- 全局 16pt 字号

### 文件结构
```
├── gui.py              # GUI 入口 (CustomTkinter, ~780行)
├── organize.py         # CLI 入口
├── config.json         # 分类规则配置
├── build.bat           # EXE 构建脚本
├── README.md / DEVLOG.md
└── lib/
    ├── classifier.py       # 文件分类
    ├── config_loader.py    # 配置加载 + 路径检测
    ├── file_ops.py         # 移动/去重/序号
    ├── history.py          # 操作记录 (撤销用)
    ├── reporter.py         # 统计报告
    └── utils.py            # 路径工具 (dev/exe兼容)
```

---

## v2.1.0 — Tkinter 稳定版 (2026-06-03)

原生 Tkinter 侧边栏 GUI，蓝色主题，浏览分类功能。

---

## v1.0.0 — CLI 初始版 (2026-06-03)

命令行工具，五分类整理 + dry-run + undo。零依赖。
