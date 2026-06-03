"""文件/文件夹分类模块。

根据配置中的扩展名映射，将文件或文件夹映射到对应的分类 key。
"""

import fnmatch
from pathlib import Path
from typing import Dict, List, Optional


def classify(
    path: Path,
    ext_map: Dict[str, str],
    folder_category: Optional[str],
    ignored_patterns: List[str],
) -> Optional[str]:
    """判断文件或文件夹应归入哪个分类。

    Args:
        path: 文件或文件夹的 Path 对象。
        ext_map: 扩展名→分类 key 的映射表（复合扩展名优先）。
        folder_category: 文件夹归入的分类 key，None 则忽略文件夹。
        ignored_patterns: fnmatch 忽略模式列表。

    Returns:
        分类 key（如 'photos'、'documents'），
        如果应忽略则返回 None。
    """
    # 检查忽略模式
    if _is_ignored(path, ignored_patterns):
        return None

    # 文件夹处理
    if path.is_dir():
        return folder_category

    # 文件：无扩展名 → 其他
    name = path.name.lower()
    if "." not in name or name.startswith(".") and name.count(".") == 1:
        # 无扩展名（如 "README"）或以点开头的纯隐藏文件（如 ".gitconfig"）
        return "others"

    # 按扩展名匹配（从最长后缀开始尝试，ext_map 已按长度降序排列）
    suffix = _get_matching_suffix(name, ext_map)
    if suffix:
        return ext_map[suffix]

    # 未匹配 → 其他
    return "others"


def _is_ignored(path: Path, patterns: List[str]) -> bool:
    """检查路径是否匹配任一忽略模式。"""
    name = path.name
    for pattern in patterns:
        if fnmatch.fnmatch(name, pattern):
            return True
    return False


def _get_matching_suffix(
    filename_lower: str, ext_map: Dict[str, str]
) -> Optional[str]:
    """从文件名中匹配最长的扩展名。

    ext_map 的 key 已按长度降序排列，所以第一个匹配的即是最长扩展名。
    例如对于 "archive.tar.gz"，先尝试 ".tar.gz"（匹配），
    而不是先匹配 ".gz"（但 .tar.gz 排在前面，先被命中）。

    Args:
        filename_lower: 小写文件名。
        ext_map: 扩展名→分类映射（按长度降序）。

    Returns:
        匹配的扩展名字符串，或 None。
    """
    for ext in ext_map:
        if filename_lower.endswith(ext):
            return ext
    return None


def get_category_name(
    cat_key: Optional[str],
    categories_config: Dict[str, dict],
) -> str:
    """获取分类的显示名称。

    Args:
        cat_key: 分类 key。
        categories_config: 完整的分类配置字典。

    Returns:
        分类的中文名称，如 '照片'、'文档'。
    """
    if cat_key is None:
        return "忽略"
    cat_info = categories_config.get(cat_key, {})
    return cat_info.get("name", cat_key)
