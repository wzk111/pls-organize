from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Optional


@dataclass(frozen=True)
class FileMeta:
    path: str
    rel_path: str
    name: str
    ext: str
    size: int
    mtime: float


@dataclass(frozen=True)
class RuleMatch:
    extension: List[str]
    filename_contains: List[str]


@dataclass(frozen=True)
class RuleAction:
    move_to: str


@dataclass(frozen=True)
class Rule:
    name: str
    match: RuleMatch
    action: RuleAction


@dataclass(frozen=True)
class PlannedOp:
    op: str  # "move"
    src: str
    dst: str
    reason: str
    confidence: float
    rule_name: Optional[str] = None


@dataclass
class Plan:
    root: str
    created_at: str
    operations: List[PlannedOp]
