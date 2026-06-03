"""输出和统计模块。"""

from typing import Any, Dict, List, Optional


class Report:
    """整理操作统计报告。"""

    def __init__(self, categories_config: Dict[str, Any]):
        self.categories_config = categories_config
        self.stats: Dict[str, Dict[str, int]] = {}
        self.skipped: List[str] = []  # 忽略的文件列表
        self.errors: List[str] = []  # 错误列表

        # 初始化统计
        for key in categories_config:
            self.stats[key] = {"files": 0, "folders": 0, "dedup": 0}
        self.stats["skipped"] = {"count": 0}

    def record_move(self, cat_key: str, is_folder: bool = False) -> None:
        """记录一次移动。"""
        if cat_key in self.stats:
            if is_folder:
                self.stats[cat_key]["folders"] += 1
            else:
                self.stats[cat_key]["files"] += 1

    def record_dedup(self, cat_key: str) -> None:
        """记录一次去重删除。"""
        if cat_key in self.stats:
            self.stats[cat_key]["dedup"] += 1

    def record_skip(self, name: str, reason: str = "") -> None:
        """记录一次跳过。"""
        self.skipped.append(f"{name}" + (f" ({reason})" if reason else ""))
        self.stats["skipped"]["count"] += 1

    def record_error(self, name: str, error: str) -> None:
        """记录一次错误。"""
        self.errors.append(f"{name}: {error}")

    @property
    def total_files(self) -> int:
        return sum(s["files"] for s in self.stats.values())

    @property
    def total_folders(self) -> int:
        return sum(s.get("folders", 0) for s in self.stats.values())

    @property
    def total_moved(self) -> int:
        return self.total_files + self.total_folders

    @property
    def total_dedup(self) -> int:
        return sum(s.get("dedup", 0) for s in self.stats.values())

    def print_summary(self) -> None:
        """打印汇总报告。"""
        print("\n" + "=" * 50)
        print("  下载文件夹整理报告")
        print("=" * 50)

        for cat_key, cat_info in self.categories_config.items():
            stat = self.stats.get(cat_key, {})
            name = cat_info.get("name", cat_key)
            files = stat.get("files", 0)
            folders = stat.get("folders", 0)
            dedup = stat.get("dedup", 0)
            parts = []
            if files > 0:
                parts.append(f"{files} 个文件")
            if folders > 0:
                parts.append(f"{folders} 个文件夹")
            if dedup > 0:
                parts.append(f"{dedup} 个去重")

            if parts:
                print(f"  [{name}] {'，'.join(parts)}")

        skipped_count = self.stats["skipped"]["count"]
        if skipped_count > 0:
            print(f"  [忽略] {skipped_count} 个")

        if self.errors:
            print(f"\n  [错误] {len(self.errors)} 个:")
            for err in self.errors:
                print(f"    ! {err}")

        print("-" * 50)
        print(f"  总计: {self.total_moved} 项已整理"
              + (f"，{self.total_dedup} 个重复已删除" if self.total_dedup > 0 else "")
              + (f"，{len(self.errors)} 个错误" if self.errors else ""))
        print("=" * 50 + "\n")


def print_dry_run(
    moves: List[Dict[str, Any]],
    categories_config: Dict[str, Any],
) -> None:
    """打印 dry-run 预览。

    Args:
        moves: 计划移动列表 [{src, dest, cat_key, is_folder, op_type}, ...]
        categories_config: 分类配置。
    """
    print("\n" + "=" * 50)
    print("  预览模式 — 不会实际修改文件")
    print("=" * 50)

    by_category: Dict[str, List[Dict]] = {}
    for m in moves:
        cat = m["cat_key"]
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(m)

    for cat_key, cat_info in categories_config.items():
        items = by_category.get(cat_key, [])
        if not items:
            continue
        name = cat_info.get("name", cat_key)
        print(f"\n  [{name}] ({len(items)} 项)")
        for m in items:
            src_name = m["src"].name
            op = m["op_type"]
            if op == "dedup":
                print(f"    {src_name}  →  去重删除（与已存在文件相同）")
            elif op == "rename":
                print(f"    {src_name}  →  {m['dest'].name}（重命名）")
            else:
                print(f"    {src_name}")

    skipped = [m for m in moves if m["cat_key"] == "skipped"]
    if skipped:
        print(f"\n  [忽略] ({len(skipped)} 项)")
        for m in skipped:
            print(f"    {m['src'].name}")

    print("\n" + "-" * 50)
    total = len([m for m in moves if m["cat_key"] != "skipped"])
    print(f"  共 {total} 项将被整理")
    print("=" * 50 + "\n")


def print_verbose_move(
    src_name: str,
    dest_name: str,
    category_name: str,
    op_type: str,
) -> None:
    """打印单条移动详情（verbose 模式）。

    Args:
        src_name: 源文件名。
        dest_name: 目标文件名。
        category_name: 分类名称。
        op_type: 操作类型。
    """
    if op_type == "dedup":
        print(f"  [-] {src_name}  →  去重删除（{category_name}）")
    elif op_type == "rename":
        print(f"  [M] {src_name}  →  {dest_name}（{category_name}）")
    else:
        print(f"  [M] {src_name}  →  {category_name}")
