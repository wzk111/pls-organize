from __future__ import annotations
import os
import time
from typing import List, Optional, Iterable
from .types import FileMeta


DEFAULT_IGNORES = {".pls-organize-journal", ".git", ".svn", ".DS_Store"}


def scan_folder(root: str, ignore_names: Optional[Iterable[str]] = None) -> List[FileMeta]:
    root = os.path.abspath(root)
    ignores = set(ignore_names or [])
    ignores |= DEFAULT_IGNORES

    out: List[FileMeta] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # skip ignored dirs
        dirnames[:] = [d for d in dirnames if d not in ignores]

        for fn in filenames:
            if fn in ignores:
                continue
            full = os.path.join(dirpath, fn)
            try:
                st = os.stat(full)
            except OSError:
                continue

            rel = os.path.relpath(full, root)
            name, ext = os.path.splitext(fn)
            out.append(
                FileMeta(
                    path=full,
                    rel_path=rel,
                    name=fn,
                    ext=ext.lower(),
                    size=int(st.st_size),
                    mtime=float(st.st_mtime),
                )
            )

    return out
