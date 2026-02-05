from __future__ import annotations
import argparse
import json
import os
from typing import Any
from rich import print

from engine.scanner import scan_folder
from engine.rules import load_rules_yaml
from engine.planner import build_plan
from engine.types import Plan, PlannedOp
from engine.executor import apply_plan, undo_last


def _write_json(path: str, obj: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def cmd_scan(args: argparse.Namespace) -> int:
    files = scan_folder(args.root)
    payload = {
        "root": os.path.abspath(args.root),
        "files": [f.__dict__ for f in files],
    }
    if args.output:
        _write_json(args.output, payload)
        print(f"[green]Wrote scan to[/green] {args.output}")
    else:
        print(payload)
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    files = scan_folder(args.root)
    rules = load_rules_yaml(args.rules)
    # plan = build_plan(args.root, files, rules, quarantine_dirname=args.quarantine)
    plan = build_plan(args.root, files, rules)

    payload = {
        "root": plan.root,
        "created_at": plan.created_at,
        "operations": [
            {
                "op": op.op,
                "from": op.src,
                "to": op.dst,
                "reason": op.reason,
                "confidence": op.confidence,
                "rule_name": op.rule_name,
            }
            for op in plan.operations
        ],
    }
    if args.output:
        _write_json(args.output, payload)
        print(f"[green]Wrote plan to[/green] {args.output}")
    else:
        print(payload)
    return 0


def _plan_from_json(obj: Any) -> Plan:
    ops = []
    for x in obj["operations"]:
        ops.append(
            PlannedOp(
                op=x["op"],
                src=x["from"],
                dst=x["to"],
                reason=x.get("reason", ""),
                confidence=float(x.get("confidence", 0.0)),
                rule_name=x.get("rule_name"),
            )
        )
    return Plan(root=obj["root"], created_at=obj["created_at"], operations=ops)


def cmd_apply(args: argparse.Namespace) -> int:
    obj = _read_json(args.plan)
    plan = _plan_from_json(obj)
    run_id, summary = apply_plan(
        plan=plan,
        journal_dir=args.journal,
        conflict_strategy=args.conflict,
        min_confidence=float(args.min_confidence),
    )
    print(f"[green]Applied[/green] run_id={run_id} summary={summary}")
    return 0 if summary["errors"] == 0 else 2


def cmd_undo(args: argparse.Namespace) -> int:
    res = undo_last(args.journal)
    if res.get("ok"):
        print(f"[green]Undo OK[/green]: {res}")
        return 0
    print(f"[red]Undo failed[/red]: {res}")
    return 2


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pls-organize")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="scan folder")
    s.add_argument("root")
    s.add_argument("-o", "--output", default=None)
    s.set_defaults(func=cmd_scan)

    pl = sub.add_parser("plan", help="create plan from rules")
    pl.add_argument("root")
    pl.add_argument("--rules", required=True)
    pl.add_argument("--quarantine", default="Quarantine")
    pl.add_argument("-o", "--output", default="plan.json")
    pl.set_defaults(func=cmd_plan)

    a = sub.add_parser("apply", help="apply a plan.json and write journal for undo")
    a.add_argument("plan")
    a.add_argument("--journal", default=".pls-organize-journal")
    a.add_argument("--conflict", choices=["rename", "skip", "overwrite"], default="rename")
    a.add_argument("--min-confidence", default="0.0")
    a.set_defaults(func=cmd_apply)

    u = sub.add_parser("undo", help="undo last run from journal")
    u.add_argument("--journal", default=".pls-organize-journal")
    u.set_defaults(func=cmd_undo)

    return p


def main() -> int:
    p = build_parser()
    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
