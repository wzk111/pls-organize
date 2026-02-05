from __future__ import annotations
from typing import List
import yaml
from .types import Rule, RuleMatch, RuleAction


class RulesError(Exception):
    pass


def load_rules_yaml(path: str) -> List[Rule]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        raise RulesError(f"Failed to read rules file: {e}") from e

    if not isinstance(data, dict) or "rules" not in data:
        raise RulesError("rules.yaml must contain top-level key: rules")

    rules_data = data["rules"]
    if not isinstance(rules_data, list):
        raise RulesError("rules must be a list")

    rules: List[Rule] = []
    for i, r in enumerate(rules_data):
        if not isinstance(r, dict):
            raise RulesError(f"Rule #{i} must be an object")

        name = r.get("name")
        match = r.get("match", {})
        action = r.get("action", {})

        if not isinstance(name, str) or not name:
            raise RulesError(f"Rule #{i} missing valid name")

        ext = match.get("extension", [])
        contains = match.get("filename_contains", [])

        if not isinstance(ext, list) or not all(isinstance(x, str) for x in ext):
            raise RulesError(f"Rule {name}: match.extension must be a list of strings")
        if not isinstance(contains, list) or not all(isinstance(x, str) for x in contains):
            raise RulesError(f"Rule {name}: match.filename_contains must be a list of strings")

        move_to = action.get("move_to")
        if not isinstance(move_to, str) or not move_to:
            raise RulesError(f"Rule {name}: action.move_to must be a string")

        rules.append(
            Rule(
                name=name,
                match=RuleMatch(extension=[x.lower() for x in ext], filename_contains=contains),
                action=RuleAction(move_to=move_to),
            )
        )
    return rules
