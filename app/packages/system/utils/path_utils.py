"""Path utilities: normalize absolute path and directory key.

These helpers centralize the rules used across file_service/sync_service:
- Absolute path always starts with '/'; keep trailing slash semantics when needed;
- Directory key does not end with '/', root represented by empty string ''.
"""

from __future__ import annotations


def norm_abs_path(p: str | None) -> str:
    s = (p or "/").strip() or "/"
    if not s.startswith("/"):
        s = "/" + s
    # keep provided trailing slash semantics to downstream callers
    return s


def norm_dir_key(p: str | None) -> str:
    s = norm_abs_path(p)
    s = s.rstrip("/")
    return "" if s == "/" else s

