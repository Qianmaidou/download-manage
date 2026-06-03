"""文件操作模块。

提供安全移动、冲突解决、哈希去重等功能。
"""

import hashlib
import re
import shutil
from pathlib import Path
from typing import Optional, Tuple


# 大文件哈希阈值：超过此大小的文件仅采样前后各 1MB
LARGE_FILE_THRESHOLD = 100 * 1024 * 1024  # 100 MB
SAMPLE_SIZE = 1024 * 1024  # 1 MB

# 冲突序号正则：检测文件名末尾的 (N) 模式
COUNTER_PATTERN = re.compile(r"^(.*?)\s*\((\d+)\)$")


def hash_file(file_path: Path) -> str:
    """计算文件的 SHA256 哈希值。

    对于大于 100MB 的文件，仅采样前 1MB + 后 1MB 以提升性能。

    Args:
        file_path: 文件路径。

    Returns:
        SHA256 十六进制字符串。
    """
    file_size = file_path.stat().st_size

    if file_size == 0:
        return "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"  # 空文件 SHA256

    hasher = hashlib.sha256()

    if file_size <= LARGE_FILE_THRESHOLD:
        # 全量哈希
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
    else:
        # 采样哈希：前 1MB + 后 1MB
        with open(file_path, "rb") as f:
            # 前 1MB
            hasher.update(f.read(SAMPLE_SIZE))
            # 跳到末尾往前 1MB
            if file_size > SAMPLE_SIZE * 2:
                f.seek(-SAMPLE_SIZE, 2)
            else:
                f.seek(SAMPLE_SIZE)
            hasher.update(f.read(SAMPLE_SIZE))

    return hasher.hexdigest()


def resolve_destination(src: Path, dest_dir: Path) -> Tuple[Path, str]:
    """解析目标路径，处理名称冲突。

    Args:
        src: 源文件路径。
        dest_dir: 目标目录路径。

    Returns:
        (目标完整路径, 操作类型):
        - "move": 直接移动（无冲突）
        - "dedup": 文件内容相同，删除源文件
        - "rename": 名称冲突但内容不同，追加序号
    """
    dest = dest_dir / src.name

    # 无冲突
    if not dest.exists():
        return dest, "move"

    # 目标已存在，比较哈希
    src_hash = hash_file(src)
    dest_hash = hash_file(dest)

    if src_hash == dest_hash:
        # 相同文件 → 去重
        return dest, "dedup"

    # 不同文件 → 找可用序号
    stem = dest.stem
    suffix = dest.suffix

    # 解析已有序号
    match = COUNTER_PATTERN.match(stem)
    if match:
        base = match.group(1)
        counter = int(match.group(2)) + 1
    else:
        base = stem
        counter = 1

    while True:
        candidate = dest_dir / f"{base} ({counter}){suffix}"
        if not candidate.exists():
            return candidate, "rename"
        # 检查是否与候选文件内容相同
        if hash_file(src) == hash_file(candidate):
            return candidate, "dedup"
        counter += 1


def safe_move(src: Path, dest_dir: Path) -> Tuple[Optional[Path], str]:
    """安全移动文件到目标目录，自动处理冲突。

    Args:
        src: 源文件路径。
        dest_dir: 目标分类目录。

    Returns:
        (目标路径或 None, 操作类型):
        - "move": 已移动
        - "dedup": 重复文件已删除源
        - "rename": 已重命名移动
        - "skip": 跳过（源即已在目标目录中）

    Raises:
        PermissionError: 文件被占用无法移动。
        OSError: 其他文件系统错误。
    """
    dest, op_type = resolve_destination(src, dest_dir)

    if op_type == "move" or op_type == "rename":
        shutil.move(str(src), str(dest))
        return dest, op_type
    elif op_type == "dedup":
        src.unlink()  # 删除重复的源文件
        return dest, op_type

    return dest, op_type


def move_folder(src: Path, dest_dir: Path) -> Tuple[Optional[Path], str]:
    """移动整个文件夹到目标目录。

    Args:
        src: 源文件夹路径。
        dest_dir: 目标分类目录。

    Returns:
        (目标路径或 None, 操作类型):
        - "move": 已移动
        - "dedup": 同名文件夹已存在且内容相同
        - "rename": 已重命名移动（内容不同）
    """
    dest = dest_dir / src.name

    # 无冲突
    if not dest.exists():
        shutil.move(str(src), str(dest))
        return dest, "move"

    # 同名文件夹已存在
    # 简单策略：如果目标已存在同名目录，追加序号
    stem = src.name
    counter = 1
    while True:
        candidate = dest_dir / f"{stem} ({counter})"
        if not candidate.exists():
            shutil.move(str(src), str(candidate))
            return candidate, "rename"
        counter += 1


def ensure_dir(path: Path) -> None:
    """确保目录存在，不存在则创建。

    Args:
        path: 目录路径。
    """
    path.mkdir(parents=True, exist_ok=True)
