"""配置加载与校验模块。

从 config.json 读取分类规则和忽略规则，构建扩展名→分类查找表。
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


# 默认配置文件路径（相对于项目根目录）
DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config.json"


class ConfigError(Exception):
    """配置错误。"""
    pass


def load_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """加载并校验配置文件。

    Args:
        config_path: 配置文件路径，默认为项目根目录下的 config.json。

    Returns:
        校验后的配置字典。

    Raises:
        ConfigError: 配置文件不存在、格式错误或缺少必要字段。
    """
    path = config_path or DEFAULT_CONFIG_PATH

    if not path.exists():
        raise ConfigError(f"配置文件不存在: {path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigError(f"配置文件 JSON 格式错误: {e}")

    _validate(config)
    return config


def _validate(config: Dict[str, Any]) -> None:
    """校验配置结构。"""
    if "categories" not in config:
        raise ConfigError("配置文件缺少 'categories' 字段")

    categories = config["categories"]
    if not isinstance(categories, dict) or len(categories) == 0:
        raise ConfigError("'categories' 必须是非空对象")

    for key, cat in categories.items():
        if "name" not in cat:
            raise ConfigError(f"分类 '{key}' 缺少 'name' 字段")
        if "extensions" not in cat:
            raise ConfigError(f"分类 '{key}' 缺少 'extensions' 字段")


def get_downloads_path(config: Dict[str, Any]) -> Path:
    """解析下载文件夹路径。

    Args:
        config: 配置字典。

    Returns:
        下载文件夹的绝对路径。
    """
    raw = config.get("downloads_path", "auto")
    if raw == "auto":
        # Windows: %USERPROFILE%/Downloads
        return Path(os.environ.get("USERPROFILE", "")) / "Downloads"
    return Path(raw).expanduser().resolve()


def build_extension_map(config: Dict[str, Any]) -> Dict[str, str]:
    """构建扩展名到分类 key 的映射表。

    复合扩展名（如 .tar.gz）优先于单扩展名匹配。
    排序规则：按扩展名长度降序，使 .tar.gz 在 .gz 之前被检查。

    Args:
        config: 配置字典。

    Returns:
        {'.png': 'photos', '.docx': 'documents', '.tar.gz': 'archives', ...}
    """
    ext_map: Dict[str, str] = {}

    for cat_key, cat_info in config["categories"].items():
        extensions = cat_info.get("extensions", [])
        for ext in extensions:
            ext_lower = ext.lower()
            if ext_lower in ext_map:
                # 如果已有映射，保留更长的扩展名（复合扩展名优先）
                existing = ext_map[ext_lower]
                if len(ext_lower) > len(existing):
                    ext_map[ext_lower] = cat_key
            else:
                ext_map[ext_lower] = cat_key

    # 按扩展名长度降序排列，确保复合扩展名先被检查
    # 返回普通 dict（Python 3.7+ 保持插入顺序）
    sorted_map = dict(
        sorted(ext_map.items(), key=lambda item: len(item[0]), reverse=True)
    )
    return sorted_map


def get_category_config(config: Dict[str, Any], cat_key: str) -> Dict[str, Any]:
    """获取指定分类的配置。

    Args:
        config: 配置字典。
        cat_key: 分类 key（如 'photos'）。

    Returns:
        该分类的配置字典，包含 name、extensions 等。
    """
    return config["categories"].get(cat_key, {})


def get_ignored_patterns(config: Dict[str, Any]) -> List[str]:
    """获取忽略模式列表。

    Args:
        config: 配置字典。

    Returns:
        忽略模式字符串列表。
    """
    return config.get("ignored_patterns", [])


def get_folder_category(config: Dict[str, Any]) -> Optional[str]:
    """获取文件夹应归入的分类 key。

    查找第一个设置了 include_folders=true 的分类。

    Args:
        config: 配置字典。

    Returns:
        分类 key，或 None（表示忽略文件夹）。
    """
    for cat_key, cat_info in config["categories"].items():
        if cat_info.get("include_folders", False):
            return cat_key
    return None
