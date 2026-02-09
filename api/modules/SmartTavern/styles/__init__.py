"""
SmartTavern 主题/外观 API 模块
提供主题文件的管理、读取和服务接口
"""

from .styles import (
    delete_theme,
    get_styles_switch,
    get_theme_asset,
    get_theme_detail,
    get_theme_entries,
    list_themes,
    update_styles_switch,
)

__all__ = [
    "delete_theme",
    "get_styles_switch",
    "get_theme_asset",
    "get_theme_detail",
    "get_theme_entries",
    "list_themes",
    "update_styles_switch",
]
