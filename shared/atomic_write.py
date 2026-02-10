"""
原子化文件写入工具。

写入临时文件后通过 os.replace 原子替换，防止进程崩溃时目标文件被截断损坏。
支持进程内 per-file 线程锁 + 跨进程 advisory file lock。
"""

from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Per-file thread lock (protects concurrent async handlers in the same process)
# ---------------------------------------------------------------------------

_file_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _get_file_lock(resolved: str) -> threading.Lock:
    with _locks_guard:
        if resolved not in _file_locks:
            _file_locks[resolved] = threading.Lock()
        return _file_locks[resolved]


# ---------------------------------------------------------------------------
# Platform-specific advisory locking
# ---------------------------------------------------------------------------

if sys.platform == "win32":
    import msvcrt

    def _flock_acquire(fd: int, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        while True:
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                return
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"无法在 {timeout}s 内获取文件锁")
                time.sleep(0.05)

    def _flock_release(fd: int) -> None:
        try:
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        except OSError:
            pass

else:
    import fcntl

    def _flock_acquire(fd: int, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"无法在 {timeout}s 内获取文件锁")
                time.sleep(0.05)

    def _flock_release(fd: int) -> None:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def atomic_write_json(
    target: Path | str,
    data: Any,
    *,
    mkdir: bool = True,
    lock_timeout: float = 5.0,
) -> None:
    """将 JSON 原子化写入 *target*。

    流程：线程锁 → advisory flock(.lock 文件) → 同目录 tempfile → json.dump → flush+fsync → os.replace。
    锁定对象为独立的 target.lock 文件而非 target 本身，确保 os.replace 替换 inode 后锁仍有效。
    *mkdir* 为 True 时自动创建父目录。
    *lock_timeout* 为获取锁的最大等待秒数，超时 raise TimeoutError。
    替换前会继承原文件权限（若存在），避免 mkstemp 的 0600 默认值收紧权限。
    """
    target = Path(target)
    if mkdir:
        target.parent.mkdir(parents=True, exist_ok=True)

    resolved = str(target.resolve())
    thr_lock = _get_file_lock(resolved)

    if not thr_lock.acquire(timeout=lock_timeout):
        raise TimeoutError(f"无法在 {lock_timeout}s 内获取线程锁: {resolved}")

    lock_fd = -1
    lock_file = resolved + ".lock"
    try:
        # Advisory file lock on a separate .lock file (stable inode across os.replace)
        lock_fd = os.open(lock_file, os.O_RDWR | os.O_CREAT, 0o644)
        _flock_acquire(lock_fd, lock_timeout)

        # Record original permissions of existing target
        try:
            orig_mode = os.stat(resolved).st_mode
        except OSError:
            orig_mode = None

        # Atomic write via temp file
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
    finally:
        if lock_fd >= 0:
            _flock_release(lock_fd)
            os.close(lock_fd)
        thr_lock.release()
