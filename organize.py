#!/usr/bin/env python3
"""下载文件夹整理工具 — 主入口。

将 Windows 下载文件夹中的文件按类型自动分类到子文件夹。
支持预览、撤销、详细输出等模式。

用法:
    python organize.py                  # 执行整理
    python organize.py --dry-run        # 预览模式
    python organize.py --undo           # 撤销最近一次整理
    python organize.py --verbose        # 详细输出
    python organize.py --quiet          # 静默模式
"""

import argparse
import os
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional

# 修复 Windows 终端中文编码问题
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 确保项目根目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.classifier import classify, get_category_name
from lib.config_loader import (
    build_extension_map,
    get_downloads_path,
    get_folder_category,
    get_ignored_patterns,
    load_config,
)
from lib.file_ops import ensure_dir, move_folder, safe_move
from lib.history import HistoryManager, OperationRecord
from lib.reporter import Report, print_dry_run, print_verbose_move


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="下载文件夹整理工具 — 将文件按类型自动分类",
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="预览模式：仅显示将要执行的操作，不实际修改文件",
    )
    parser.add_argument(
        "--undo",
        action="store_true",
        help="撤销最近一次整理操作",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="显示每个文件的操作详情",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="静默模式：仅输出错误信息",
    )
    return parser.parse_args()


def scan_items(downloads: Path) -> List[Path]:
    """扫描下载文件夹中的所有顶层文件和文件夹。

    按名称排序（文件夹优先，然后文件）。

    Args:
        downloads: 下载文件夹路径。

    Returns:
        排序后的 Path 列表。
    """
    if not downloads.exists():
        print(f"错误: 下载文件夹不存在: {downloads}", file=sys.stderr)
        sys.exit(1)

    all_items = list(downloads.iterdir())
    # 文件夹优先，然后文件，各自按名称排序
    dirs = sorted([p for p in all_items if p.is_dir()])
    files = sorted([p for p in all_items if p.is_file()])
    return dirs + files


def do_organize(
    downloads: Path,
    config: dict,
    ext_map: Dict[str, str],
    folder_category: Optional[str],
    ignored_patterns: List[str],
    history_mgr: HistoryManager,
    dry_run: bool = False,
    verbose: bool = False,
) -> None:
    """执行文件整理。

    Args:
        downloads: 下载文件夹路径。
        config: 完整配置。
        ext_map: 扩展名→分类映射表。
        folder_category: 文件夹应归入的分类 key。
        ignored_patterns: 忽略模式列表。
        history_mgr: 历史记录管理器。
        dry_run: 是否为预览模式。
        verbose: 是否详细输出。
    """
    categories_config = config["categories"]
    report = Report(categories_config)
    record = OperationRecord()
    dry_run_moves: List[dict] = []

    # 分类目录名集合：这些目录本身不应被整理
    category_names = {cat["name"] for cat in categories_config.values()}

    items = scan_items(downloads)

    # 过滤掉分类目录自身
    items = [p for p in items if p.name not in category_names or not p.is_dir()]

    if not items:
        print("下载文件夹为空，无需整理。")
        return

    if not dry_run and not verbose:
        print(f"正在整理 {len(items)} 个项目...")

    for item in items:
        # 分类
        cat_key = classify(item, ext_map, folder_category, ignored_patterns)

        if cat_key is None:
            # 应忽略
            report.record_skip(item.name)
            if dry_run:
                dry_run_moves.append({
                    "src": item, "dest": None, "cat_key": "skipped",
                    "is_folder": False, "op_type": "skip",
                })
            if verbose:
                print(f"  [S] {item.name}  →  忽略")
            continue

        cat_name = get_category_name(cat_key, categories_config)
        dest_dir = downloads / cat_name
        is_folder = item.is_dir()

        if dry_run:
            # 预览：不实际修改任何文件或目录，仅记录计划
            op_type = "move"
            # 检查冲突（不创建目录）
            if dest_dir.exists() and (dest_dir / item.name).exists():
                try:
                    from lib.file_ops import resolve_destination
                    _, op_type = resolve_destination(item, dest_dir)
                except Exception:
                    pass
            dry_run_moves.append({
                "src": item, "dest": dest_dir, "cat_key": cat_key,
                "is_folder": is_folder, "op_type": op_type,
            })
        else:
            # 实际执行
            try:
                ensure_dir(dest_dir)

                if is_folder:
                    result, op_type = move_folder(item, dest_dir)
                else:
                    result, op_type = safe_move(item, dest_dir)

                # 记录
                if op_type == "dedup":
                    report.record_dedup(cat_key)
                    record.add_move(item, result, op_type)
                else:
                    report.record_move(cat_key, is_folder=is_folder)
                    record.add_move(item, result, op_type)

                if verbose:
                    dest_display = result.name if result else ""
                    print_verbose_move(item.name, dest_display, cat_name, op_type)

            except (PermissionError, OSError) as e:
                report.record_error(item.name, str(e))
                if verbose:
                    print(f"  [!] {item.name}  →  错误: {e}")

    # 输出结果
    if dry_run:
        print_dry_run(dry_run_moves, categories_config)
    else:
        # 保存历史记录
        if record.count > 0:
            history_mgr.save_record(record)

        if not verbose:
            report.print_summary()
        else:
            print()  # 换行
            report.print_summary()


def do_undo(
    history_mgr: HistoryManager,
    downloads_root: Path,
    category_names: set,
    verbose: bool = False,
) -> None:
    """撤销最近一次整理操作。

    Args:
        history_mgr: 历史记录管理器。
        downloads_root: 下载文件夹根目录。
        category_names: 分类目录名集合（用于清理空目录）。
        verbose: 是否详细输出。
    """
    last = history_mgr.get_last_operation()
    if last is None:
        print("没有可撤销的操作。")
        return

    moves = last.get("moves", [])
    deleted = last.get("deleted", [])
    time_str = last.get("time", "未知时间")

    print(f"将撤销 {time_str} 的整理操作（{len(moves)} 项移动，{len(deleted)} 项去重删除）。")

    # 注意：无法恢复已删除的重复文件（去重删除的文件已永久删除）
    if deleted:
        print(f"警告: {len(deleted)} 个去重删除的文件无法恢复（已永久删除）。")

    # 逆向移动
    success = 0
    failed = 0
    for entry in reversed(moves):
        op_type = entry.get("type", "")
        src_str = entry.get("from", "")
        dest_str = entry.get("to", "")

        if not src_str or not dest_str:
            continue

        src = Path(src_str)
        dest = Path(dest_str)

        if op_type == "dedup":
            # 去重操作：源文件已被删除，无法恢复
            continue

        try:
            if dest.exists():
                # 确保父目录存在
                ensure_dir(src.parent)
                shutil.move(str(dest), str(src))
                if verbose:
                    print(f"  [U] {dest.name}  →  {src.name}")
                success += 1
            else:
                if verbose:
                    print(f"  [!] {dest.name}  →  不存在，跳过")
                failed += 1
        except (PermissionError, OSError) as e:
            print(f"  [!] {dest.name}  →  撤销失败: {e}")
            failed += 1

    # 移除历史记录
    history_mgr.pop_last_operation()

    print(f"\n撤销完成: {success} 项已恢复" + (f"，{failed} 项失败" if failed else ""))

    # 尝试清理空目录
    _cleanup_empty_dirs(downloads_root, category_names)


def _cleanup_empty_dirs(root: Path, category_names: set) -> None:
    """清理空的分类目录。

    Args:
        root: 下载文件夹根目录。
        category_names: 分类目录名集合。
    """
    if not root.exists():
        return
    for item in root.iterdir():
        if item.is_dir() and item.name in category_names:
            try:
                # 检查是否为空
                if not any(item.iterdir()):
                    item.rmdir()
            except OSError:
                pass


def main() -> None:
    """主函数。"""
    args = parse_args()

    # 加载配置
    try:
        config = load_config()
    except Exception as e:
        print(f"配置加载失败: {e}", file=sys.stderr)
        sys.exit(1)

    downloads = get_downloads_path(config)
    ext_map = build_extension_map(config)
    folder_category = get_folder_category(config)
    ignored_patterns = get_ignored_patterns(config)
    categories_config = config["categories"]

    # 历史记录管理器
    history_path = Path(__file__).resolve().parent / config.get(
        "history_file", "history.json"
    )
    history_mgr = HistoryManager(history_path)

    # 执行操作
    if args.undo:
        category_names = {cat["name"] for cat in categories_config.values()}
        do_undo(history_mgr, downloads, category_names, verbose=args.verbose)
    else:
        if not args.quiet and not args.dry_run:
            print(f"下载文件夹: {downloads}")
            print(f"分类目录: {', '.join(c['name'] for c in categories_config.values())}")

        do_organize(
            downloads=downloads,
            config=config,
            ext_map=ext_map,
            folder_category=folder_category,
            ignored_patterns=ignored_patterns,
            history_mgr=history_mgr,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )


if __name__ == "__main__":
    main()
