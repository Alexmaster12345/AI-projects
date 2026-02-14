from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass(frozen=True)
class Rule:
    rule_id: str
    title: str
    severity: str
    when: Dict[str, Any]
    mitre: Dict[str, Any]


def load_rules(rules_path: Path) -> List[Rule]:
    data = yaml.safe_load(rules_path.read_text(encoding="utf-8")) or {}
    items = data.get("rules", [])
    rules: List[Rule] = []

    for item in items:
        rule_id = str(item.get("id", ""))
        if not rule_id:
            continue

        mitre = item.get("mitre")
        if not isinstance(mitre, dict):
            mitre = {}
        rules.append(
            Rule(
                rule_id=rule_id,
                title=str(item.get("title", rule_id)),
                severity=str(item.get("severity", "low")),
                when=item.get("when", {}),
                mitre=mitre,
            )
        )
    return rules


def _get_field(event: Dict[str, Any], field: str) -> Optional[str]:
    if field in event:
        val = event.get(field)
    else:
        fields = event.get("fields") or {}
        val = fields.get(field)

    if val is None:
        return None
    return str(val)


def _eval_predicate(event: Dict[str, Any], predicate: Dict[str, Any]) -> bool:
    if "contains" in predicate:
        spec = predicate["contains"]
        field = spec.get("field")
        value = spec.get("value")
        if not field or value is None:
            return False
        hay = _get_field(event, str(field))
        if hay is None:
            return False
        return str(value) in hay

    if "equals" in predicate:
        spec = predicate["equals"]
        field = spec.get("field")
        value = spec.get("value")
        if not field:
            return False
        actual = _get_field(event, str(field))
        if actual is None:
            return False
        return actual == str(value)

    if "regex" in predicate:
        spec = predicate["regex"]
        field = spec.get("field")
        pattern = spec.get("pattern")
        if not field or not pattern:
            return False
        text = _get_field(event, str(field))
        if text is None:
            return False
        return re.search(str(pattern), text) is not None

    return False


def _eval_when(event: Dict[str, Any], when: Any) -> bool:
    if when is None:
        return False

    if isinstance(when, dict):
        if "all" in when:
            items = when["all"] or []
            return all(_eval_when(event, item) for item in items)

        if "any" in when:
            items = when["any"] or []
            return any(_eval_when(event, item) for item in items)

        # Otherwise treat as a leaf predicate
        return _eval_predicate(event, when)

    if isinstance(when, list):
        return all(_eval_when(event, item) for item in when)

    return False


def match_rules(event: Dict[str, Any], rules: List[Rule]) -> List[Dict[str, Any]]:
    matches: List[Dict[str, Any]] = []

    for rule in rules:
        try:
            ok = _eval_when(event, rule.when)
        except Exception:
            ok = False

        if ok:
            matches.append(
                {
                    "rule_id": rule.rule_id,
                    "title": rule.title,
                    "severity": rule.severity,
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "details": {
                        "matched_on": rule.when,
                        "mitre": rule.mitre,
                    },
                }
            )

    return matches
