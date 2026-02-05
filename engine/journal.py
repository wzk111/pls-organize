from __future__ import annotations
import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional


def ensure_journal_dir(path: str) -> str:
    path = os.path.abspath(path)
    os.makedirs(path, exist_ok=True)
    return path


def journal_file_for_run(journal_dir: str, run_id: str) -> str:
    return os.path.join(journal_dir, f"{run_id}.json")


def list_runs(journal_dir: str) -> List[str]:
    if not os.path.isdir(journal_dir):
        return []
    runs = []
    for fn in os.listdir(journal_dir):
        if fn.endswith(".json"):
            runs.append(fn[:-5])
    runs.sort()
    return runs


def latest_run_id(journal_dir: str) -> Optional[str]:
    runs = list_runs(journal_dir)
    return runs[-1] if runs else None


def write_journal(journal_dir: str, run_id: str, payload: Dict[str, Any]) -> str:
    ensure_journal_dir(journal_dir)
    path = journal_file_for_run(journal_dir, run_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


def read_journal(journal_dir: str, run_id: str) -> Dict[str, Any]:
    path = journal_file_for_run(journal_dir, run_id)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def delete_journal(journal_dir: str, run_id: str) -> None:
    path = journal_file_for_run(journal_dir, run_id)
    if os.path.exists(path):
        os.remove(path)


def new_run_id() -> str:
    return datetime.now().strftime("%Y%m%dT%H%M%S")
