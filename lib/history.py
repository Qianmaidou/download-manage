"""操作历史记录模块。

记录每次整理的移动操作到 JSON 文件，支持撤销。
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class OperationRecord:
    """单次整理操作的记录。"""

    def __init__(self):
        self.time: str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.moves: List[Dict[str, str]] = []  # [{from, to, type}, ...]
        self.deleted: List[str] = []  # 去重删除的文件列表

    def add_move(self, src: Path, dest: Optional[Path], op_type: str) -> None:
        """记录一次移动操作。

        Args:
            src: 源路径。
            dest: 目标路径（dedup 时为目标已存在的路径）。
            op_type: 操作类型（move, rename, dedup）。
        """
        entry = {
            "from": str(src),
            "to": str(dest) if dest else "",
            "type": op_type,
        }
        self.moves.append(entry)

        if op_type == "dedup":
            self.deleted.append(str(src))

    def to_dict(self) -> Dict[str, Any]:
        """转为可序列化的字典。"""
        return {
            "time": self.time,
            "moves": self.moves,
            "deleted": self.deleted,
        }

    @property
    def count(self) -> int:
        return len(self.moves)


class HistoryManager:
    """操作历史管理器。"""

    def __init__(self, history_path: Path):
        self.path = history_path

    def load_all(self) -> List[Dict[str, Any]]:
        """加载全部历史记录。

        Returns:
            操作记录列表，按时间顺序。
        """
        if not self.path.exists():
            return []
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("operations", [])
        except (json.JSONDecodeError, KeyError):
            return []

    def save_record(self, record: OperationRecord) -> None:
        """追加一条操作记录。

        Args:
            record: 本次操作记录。
        """
        all_records = self.load_all()
        all_records.append(record.to_dict())

        data = {"operations": all_records}
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_last_operation(self) -> Optional[Dict[str, Any]]:
        """获取最近一次操作记录。

        Returns:
            最近的记录字典，或 None。
        """
        all_records = self.load_all()
        if not all_records:
            return None
        return all_records[-1]

    def pop_last_operation(self) -> Optional[Dict[str, Any]]:
        """移除并返回最近一次操作记录。

        Returns:
            最近的记录字典，或 None。
        """
        all_records = self.load_all()
        if not all_records:
            return None
        last = all_records.pop()
        data = {"operations": all_records}
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return last

    def clear(self) -> None:
        """清空所有历史记录。"""
        data = {"operations": []}
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
