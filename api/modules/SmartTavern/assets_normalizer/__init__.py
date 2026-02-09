"""
SmartTavern.assets_normalizer 包
- 封装层：assets_normalizer.py（注册 6 个 API）
- 实现层：impl.py（提取/合并核心逻辑）
"""

from .assets_normalizer import (
    extract_character_regex,
    extract_character_world_book,
    extract_preset_regex,
    merge_regex,
    merge_world_books,
    normalize,
)
