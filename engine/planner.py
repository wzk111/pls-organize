from __future__ import annotations
import os
import time
from datetime import datetime
from typing import List, Optional
from .types import FileMeta, Rule, PlannedOp, Plan


def _format_dest(template: str, mtime: float) -> str:
    dt = datetime.fromtimestamp(mtime)
    year = f"{dt.year:04d}"
    month = f"{dt.month:02d}"
    day = f"{dt.day:02d}"
    return (
        template.replace("{year}", year)
        .replace("{month}", month)
        .replace("{day}", day)
    )


def _match_rule(file: FileMeta, rule: Rule) -> Optional[float]:
    # return confidence if match else None
    ext_ok = (not rule.match.extension) or (file.ext in rule.match.extension)
    if not ext_ok:
        return None

    tokens = [t.strip().lower() for t in rule.match.filename_contains if t.strip()]
    if not tokens:
        # extension-only match is weaker
        return 0.7 if rule.match.extension else 0.5

    lower_name = file.name.lower()
    hit = sum(1 for t in tokens if t in lower_name)
    if hit == 0:
        return None

    # confidence scales by fraction matched
    return min(0.95, 0.75 + 0.2 * (hit / max(1, len(tokens))))


def build_plan(
    root: str,
    files: List[FileMeta],
    rules: List[Rule],
    quarantine_dirname: str = "Quarantine",
) -> Plan:
    root = os.path.abspath(root)
    ops: List[PlannedOp] = []

    for f in files:
        best_rule: Optional[Rule] = None
        best_conf: float = -1.0

        for r in rules:
            conf = _match_rule(f, r)
            if conf is None:
                continue
            if conf > best_conf:
                best_conf = conf
                best_rule = r

        if best_rule is None:
            # unmatched → quarantine (low confidence)
            dest_dir = os.path.join(root, quarantine_dirname)
            dst = os.path.join(dest_dir, f.name)
            ops.append(
                PlannedOp(
                    op="move",
                    src=f.path,
                    dst=dst,
                    reason="Unmatched by rules → quarantine",
                    confidence=0.2,
                    rule_name=None,
                )
            )
            continue

        rel_dest_dir = _format_dest(best_rule.action.move_to, f.mtime)
        dest_dir = os.path.join(root, rel_dest_dir)
        dst = os.path.join(dest_dir, f.name)
        ops.append(
            PlannedOp(
                op="move",
                src=f.path,
                dst=dst,
                reason=f"Matched rule: {best_rule.name}",
                confidence=float(best_conf),
                rule_name=best_rule.name,
            )
        )

    return Plan(
        root=root,
        created_at=datetime.now().isoformat(timespec="seconds"),
        operations=ops,
    )
