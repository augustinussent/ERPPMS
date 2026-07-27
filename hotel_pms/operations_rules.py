from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable


@dataclass(frozen=True)
class InspectionResult:
    score: float
    passed: bool
    critical_failures: int
    completed_items: int
    total_applicable_items: int


def housekeeping_priority_score(
    *,
    guest_waiting: bool = False,
    minutes_to_next_arrival: int | None = None,
    task_type: str = "Checkout Clean",
    vip: bool = False,
) -> int:
    """Return a deterministic queue score; higher values are cleaned first."""
    score = 0
    if guest_waiting:
        score += 1000
    if vip:
        score += 350
    score += {
        "Checkout Clean": 300,
        "Post-Maintenance Cleaning": 280,
        "Reclean": 275,
        "Stayover Clean": 160,
        "Pickup": 140,
        "Turndown": 100,
        "Deep Clean": 40,
        "Inspection": 20,
    }.get(task_type or "", 80)
    if minutes_to_next_arrival is not None:
        if minutes_to_next_arrival <= 0:
            score += 700
        elif minutes_to_next_arrival <= 60:
            score += 500
        elif minutes_to_next_arrival <= 180:
            score += 300
        elif minutes_to_next_arrival <= 360:
            score += 150
        elif minutes_to_next_arrival <= 720:
            score += 50
    return score


def elapsed_minutes(started_at: datetime | None, ended_at: datetime | None, pause_minutes: float = 0) -> float:
    if not started_at or not ended_at or ended_at <= started_at:
        return 0.0
    return round(max(((ended_at - started_at).total_seconds() / 60) - float(pause_minutes or 0), 0), 2)


def calculate_inspection_result(items: Iterable[dict], pass_score: float = 90) -> InspectionResult:
    applicable = []
    critical_failures = 0
    completed = 0
    earned = 0.0
    possible = 0.0
    for row in items:
        result = (row.get("result") or "Pending").strip()
        if result == "Not Applicable":
            continue
        weight = float(row.get("weight") or 1)
        applicable.append(row)
        possible += weight
        if result in ("OK", "Reported to Engineering"):
            completed += 1
            if result == "OK":
                earned += weight
        elif result == "Not OK":
            completed += 1
            if row.get("is_critical"):
                critical_failures += 1
    score = round((earned / possible * 100) if possible else 100.0, 2)
    passed = score >= float(pass_score or 0) and critical_failures == 0 and completed == len(applicable)
    return InspectionResult(score, passed, critical_failures, completed, len(applicable))


def get_sla_minutes(priority: str, settings: dict) -> tuple[int, int]:
    key = (priority or "Medium").split(" - ", 1)[0].lower()
    key = {"critical": "critical", "high": "high", "medium": "medium", "low": "low"}.get(key, "medium")
    response = int(settings.get(f"{key}_response_minutes") or {"critical": 10, "high": 20, "medium": 60, "low": 240}[key])
    resolution = int(settings.get(f"{key}_resolution_minutes") or {"critical": 60, "high": 180, "medium": 480, "low": 1440}[key])
    return response, resolution


def calculate_sla_status(
    *,
    now: datetime,
    response_due_at: datetime | None,
    resolution_due_at: datetime | None,
    acknowledged_at: datetime | None,
    resolved_at: datetime | None,
) -> str:
    if resolved_at:
        if resolution_due_at and resolved_at > resolution_due_at:
            return "Resolution Breached"
        if response_due_at and acknowledged_at and acknowledged_at > response_due_at:
            return "Response Breached"
        return "Met"
    if resolution_due_at and now > resolution_due_at:
        return "Resolution Breached"
    if not acknowledged_at and response_due_at and now > response_due_at:
        return "Response Breached"
    return "On Track"


def should_create_sop_candidate(*, repeat_count: int, threshold: int, has_learning: bool) -> bool:
    return bool(has_learning and int(repeat_count or 0) >= max(int(threshold or 1), 1))
