from __future__ import annotations
import os
import shutil
from typing import Dict, Any, List, Tuple
from .types import Plan, PlannedOp
from .journal import new_run_id, write_journal, read_journal, latest_run_id, delete_journal

def _is_within_root(path: str, root: str) -> bool:
    path = os.path.abspath(path)
    root = os.path.abspath(root)
    try:
        common = os.path.commonpath([path, root])
    except ValueError:
        return False
    return common == root


def _ensure_parent_and_track(dst: str, root: str, created_dirs: set[str]) -> None:
    """
    Create parent directories for dst and record any NEW dirs created (within root).
    """
    parent = os.path.abspath(os.path.dirname(dst))
    root = os.path.abspath(root)

    if not _is_within_root(parent, root):
        # Safety guard: we never create folders outside root
        return

    # Build list of parents from root -> leaf to detect which were missing
    to_create = []
    cur = parent
    while _is_within_root(cur, root) and cur != root:
        if os.path.exists(cur):
            break
        to_create.append(cur)
        cur = os.path.dirname(cur)

    # Create from top to bottom
    for d in reversed(to_create):
        os.makedirs(d, exist_ok=True)
        created_dirs.add(d)

    # Ensure parent exists (in case it partially existed)
    os.makedirs(parent, exist_ok=True)


def _ensure_parent(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


def _resolve_conflict(dst: str, strategy: str) -> str:
    """
    strategy:
      - "rename": if exists, append (1), (2)...
      - "skip": return "" to indicate skip
      - "overwrite": keep dst
    """
    if not os.path.exists(dst):
        return dst

    if strategy == "overwrite":
        return dst
    if strategy == "skip":
        return ""

    # rename
    base, ext = os.path.splitext(dst)
    i = 1
    while True:
        candidate = f"{base} ({i}){ext}"
        if not os.path.exists(candidate):
            return candidate
        i += 1


def apply_plan(
    plan: Plan,
    journal_dir: str,
    conflict_strategy: str = "rename",
    min_confidence: float = 0.0,
) -> Tuple[str, Dict[str, Any]]:
    """
    Apply operations >= min_confidence, record a journal for undo.
    Returns (run_id, summary)
    """
    run_id = new_run_id()

    executed: List[Dict[str, Any]] = []
    created_dirs: set[str] = set()
    skipped: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    for op in plan.operations:
        if op.confidence < min_confidence:
            skipped.append({"src": op.src, "dst": op.dst, "reason": "below min_confidence"})
            continue

        if op.op != "move":
            skipped.append({"src": op.src, "dst": op.dst, "reason": "unsupported op"})
            continue

        if not os.path.exists(op.src):
            skipped.append({"src": op.src, "dst": op.dst, "reason": "source missing"})
            continue

        final_dst = _resolve_conflict(op.dst, conflict_strategy)
        if final_dst == "":
            skipped.append({"src": op.src, "dst": op.dst, "reason": "conflict skip"})
            continue

        try:
            _ensure_parent_and_track(final_dst, plan.root, created_dirs)
            # overwrite means remove target first
            if conflict_strategy == "overwrite" and os.path.exists(final_dst):
                os.remove(final_dst)

            shutil.move(op.src, final_dst)
            executed.append({"type": "move", "from": op.src, "to": final_dst})
        except Exception as e:
            errors.append({"src": op.src, "dst": final_dst, "error": str(e)})

    payload = {
        "run_id": run_id,
        "root": plan.root,
        "conflict_strategy": conflict_strategy,
        "min_confidence": min_confidence,
        "executed": executed,
        "skipped": skipped,
        "errors": errors,
        "created_dirs": sorted(created_dirs),
    }
    write_journal(journal_dir, run_id, payload)

    summary = {
        "run_id": run_id,
        "moved": len(executed),
        "skipped": len(skipped),
        "errors": len(errors),
    }
    return run_id, summary


def undo_last(journal_dir: str) -> Dict[str, Any]:
    run_id = latest_run_id(journal_dir)
    if not run_id:
        return {"ok": False, "message": "No journal runs found."}
    return undo_run(journal_dir, run_id)


def undo_run(journal_dir: str, run_id: str) -> Dict[str, Any]:
    data = read_journal(journal_dir, run_id)
    executed = data.get("executed", [])

    undone = 0
    errors = []

    # reverse order
    for op in reversed(executed):
        if op.get("type") != "move":
            continue
        src = op.get("to")   # current location
        dst = op.get("from") # original location

        try:
            if not os.path.exists(src):
                continue
            os.makedirs(os.path.dirname(dst), exist_ok=True)

            # if dst exists, we rename the restored file
            if os.path.exists(dst):
                base, ext = os.path.splitext(dst)
                i = 1
                while os.path.exists(f"{base} (restored {i}){ext}"):
                    i += 1
                dst = f"{base} (restored {i}){ext}"

            shutil.move(src, dst)
            undone += 1
        except Exception as e:
            errors.append({"from": src, "to": dst, "error": str(e)})

    # If no errors, we can remove journal entry (optional).
    if not errors:
        delete_journal(journal_dir, run_id)

        # Cleanup empty directories that were created during apply
    created_dirs = data.get("created_dirs", [])
    root = os.path.abspath(data.get("root", ""))

    # Delete deepest paths first (so child folders removed before parents)
    created_dirs = sorted(
        (os.path.abspath(d) for d in created_dirs),
        key=lambda p: p.count(os.sep),
        reverse=True
    )

    dir_deleted = 0
    dir_errors = []

    for d in created_dirs:
        try:
            if not d or not os.path.isdir(d):
                continue
            if not _is_within_root(d, root):
                continue
            # Only remove if empty
            if not os.listdir(d):
                os.rmdir(d)
                dir_deleted += 1
        except Exception as e:
            dir_errors.append({"dir": d, "error": str(e)})

    if dir_errors:
        # don't fail the whole undo; just report
        errors.extend(dir_errors)

    return {
        "ok": len(errors) == 0,
        "run_id": run_id,
        "undone": undone,
        "dirs_deleted": dir_deleted,
        "errors": errors,
    }
