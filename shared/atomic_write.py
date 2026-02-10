"""
原子化文件写入工具。

写入临时文件后通过 os.replace 原子替换，防止进程崩溃时目标文件被截断损坏。
"""

from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any


def atomic_write_json(target: Path | str, data: Any, *, mkdir: bool = True) -> None:
    """将 JSON 原子化写入 *target*。

    流程：同目录 tempfile → json.dump → flush+fsync → os.replace。
    *mkdir* 为 True 时自动创建父目录。
    替换前会继承原文件权限（若存在），避免 mkstemp 的 0600 默认值收紧权限。
    """
    target = Path(target)
    if mkdir:
        target.parent.mkdir(parents=True, exist_ok=True)

    # 记录原文件权限
    try:
        orig_mode = target.stat().st_mode
    except OSError:
        orig_mode = None

    fd, tmp_path = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())

        if orig_mode is not None:
            os.chmod(tmp_path, stat.S_IMODE(orig_mode))

        os.replace(tmp_path, target)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
