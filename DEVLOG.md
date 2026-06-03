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
