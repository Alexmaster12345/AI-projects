from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class MitreTactic:
    name: str
    expected_technique_count: int


TACTICS: List[MitreTactic] = [
    MitreTactic("Reconnaissance", 11),
    MitreTactic("Resource Development", 8),
    MitreTactic("Initial Access", 11),
    MitreTactic("Execution", 17),
    MitreTactic("Persistence", 23),
    MitreTactic("Privilege Escalation", 14),
    MitreTactic("Defense Evasion", 47),
    MitreTactic("Credential Access", 17),
    MitreTactic("Discovery", 34),
    MitreTactic("Lateral Movement", 9),
    MitreTactic("Collection", 17),
    MitreTactic("Command and Control", 18),
    MitreTactic("Exfiltration", 9),
    MitreTactic("Impact", 15),
]


_COUNTS_SUFFIX_RE = re.compile(r"\s*\(\d+\)\s*$")


def _normalize_technique_name(line: str) -> Optional[str]:
    s = (line or "").strip()
    if not s:
        return None

    # Skip separators.
    if s == "=":
        return None

    # Skip the header lines if present.
    if "\t" in s:
        return None

    if s.lower().endswith("techniques"):
        return None

    # Remove trailing counts like "(3)".
    s = _COUNTS_SUFFIX_RE.sub("", s).strip()
    if not s:
        return None

    return s


def load_attack_raw_text(raw_path: Path) -> str:
    return raw_path.read_text(encoding="utf-8", errors="replace")


def build_attack_catalog_from_raw_text(raw_text: str) -> Dict[str, Any]:
    techniques: List[str] = []
    for line in (raw_text or "").splitlines():
        name = _normalize_technique_name(line)
        if name is None:
            continue
        techniques.append(name)

    # Segment techniques by tactic counts, preserving order.
    segments: Dict[str, List[str]] = {}
    idx = 0
    for tactic in TACTICS:
        segments[tactic.name] = techniques[idx : idx + tactic.expected_technique_count]
        idx += tactic.expected_technique_count

    leftover = techniques[idx:]

    catalog = {
        "ok": True,
        "tactics": [
            {
                "name": t.name,
                "expected_technique_count": t.expected_technique_count,
                "techniques": segments.get(t.name, []),
                "parsed_technique_count": len(segments.get(t.name, [])),
            }
            for t in TACTICS
        ],
        "parsed_total_techniques": sum(len(segments.get(t.name, [])) for t in TACTICS),
        "leftover_lines": leftover,
        "leftover_count": len(leftover),
    }

    # If parsing went off the rails, still return something predictable.
    if any(len(segments.get(t.name, [])) != t.expected_technique_count for t in TACTICS):
        catalog["ok"] = False
        catalog["error"] = "parsed technique counts did not match expected tactic counts"

    return catalog


def build_attack_catalog(raw_path: Path) -> Dict[str, Any]:
    return build_attack_catalog_from_raw_text(load_attack_raw_text(raw_path))
