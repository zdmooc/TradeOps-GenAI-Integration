from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

VALID_STATUSES = {"SATISFIED", "PARTIAL", "PENDING", "NOT_APPLICABLE"}
VALID_EVIDENCE_CLASSES = {
    "CI",
    "DOCUMENTED",
    "OFFLINE_CI",
    "LIVE",
    "OPERATIONAL",
    "DESIGNED",
}
REQUIRED_CRITERIA = (
    "LIVE_MULTI_SOURCE_REPLAY",
    "DATA_QUALITY_ENGINE",
    "TECHNICAL_PATTERN_REGIME",
    "BACKTEST_OOS_WALKFORWARD",
    "ML_CALIBRATION_IF_PROBABILISTIC",
    "SPECIALIZED_AGENTS_CONFLICT",
    "SECURE_MCP_TOOL_BOUNDARY",
    "DETERMINISTIC_RISK_HITL",
    "PAPER_SHADOW_100_OUTCOMES",
    "OBSERVABILITY_SECURITY_LIVE",
    "OPENSHIFT_AZURE_DEPLOYMENT",
    "RESILIENCE_FINOPS_GREENOPS_VERIFIED",
    "INTERVIEW_DEMO_PACK",
    "BANK_INSURANCE_TRANSPOSITION",
)
CONDITIONAL_NOT_APPLICABLE = {"ML_CALIBRATION_IF_PROBABILISTIC"}
LIVE_EVIDENCE_CRITERIA = {
    "LIVE_MULTI_SOURCE_REPLAY",
    "OBSERVABILITY_SECURITY_LIVE",
    "OPENSHIFT_AZURE_DEPLOYMENT",
    "RESILIENCE_FINOPS_GREENOPS_VERIFIED",
}
PAPER_SHADOW_CRITERION = "PAPER_SHADOW_100_OUTCOMES"
REAL_MARKET_SOURCES = {"LIVE_MARKET", "RECORDED_REAL_MARKET"}


@dataclass(frozen=True)
class GraduationReport:
    status: str
    satisfied: tuple[str, ...]
    not_applicable: tuple[str, ...]
    blockers: tuple[str, ...]
    errors: tuple[str, ...]
    paper_shadow_valid_outcomes: int
    required_paper_shadow_outcomes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "satisfied": list(self.satisfied),
            "not_applicable": list(self.not_applicable),
            "blockers": list(self.blockers),
            "errors": list(self.errors),
            "paper_shadow_valid_outcomes": self.paper_shadow_valid_outcomes,
            "required_paper_shadow_outcomes": self.required_paper_shadow_outcomes,
        }


def load_manifest(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        loaded = json.load(handle)
    if not isinstance(loaded, dict):
        raise ValueError("graduation manifest must be a JSON object")
    return loaded


def _aware_iso8601(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _valid_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _valid_paper_shadow_record(record: Any) -> bool:
    if not isinstance(record, dict):
        return False
    if not isinstance(record.get("signal_id"), str) or not record["signal_id"].strip():
        return False
    if record.get("mode") not in {"PAPER", "SHADOW"}:
        return False
    if record.get("source") not in REAL_MARKET_SOURCES:
        return False
    if record.get("state") != "CLOSED":
        return False
    if not _aware_iso8601(record.get("observed_at")):
        return False
    if not _aware_iso8601(record.get("closed_at")):
        return False
    if not _valid_number(record.get("realized_r")):
        return False
    if not isinstance(record.get("evidence_ref"), str) or not record["evidence_ref"].strip():
        return False
    return True


def count_valid_paper_shadow_records(path: str | Path) -> int:
    records_path = Path(path)
    if not records_path.exists():
        return 0

    unique_ids: set[str] = set()
    with records_path.open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid JSONL paper/shadow record at line {line_number}: {exc.msg}"
                ) from exc
            if _valid_paper_shadow_record(record):
                unique_ids.add(record["signal_id"])
    return len(unique_ids)


def _check_repo_refs(refs: list[Any], repo_root: Path, errors: list[str], criterion_id: str) -> None:
    for ref in refs:
        if not isinstance(ref, str) or not ref.strip():
            errors.append(f"{criterion_id}: evidence_refs contains an invalid reference")
            continue
        if ref.startswith("repo:"):
            relative = ref.removeprefix("repo:")
            if not relative or not (repo_root / relative).exists():
                errors.append(f"{criterion_id}: missing repository evidence {relative!r}")


def evaluate_manifest(manifest: dict[str, Any], repo_root: str | Path = ".") -> GraduationReport:
    root = Path(repo_root)
    errors: list[str] = []
    blockers: list[str] = []
    satisfied: list[str] = []
    not_applicable: list[str] = []

    if manifest.get("schema_version") != "1.0":
        errors.append("schema_version must be '1.0'")

    criteria = manifest.get("criteria")
    if not isinstance(criteria, list):
        criteria = []
        errors.append("criteria must be a list")

    by_id: dict[str, dict[str, Any]] = {}
    for criterion in criteria:
        if not isinstance(criterion, dict):
            errors.append("every criterion must be an object")
            continue
        criterion_id = criterion.get("id")
        if not isinstance(criterion_id, str) or not criterion_id:
            errors.append("every criterion must have a non-empty id")
            continue
        if criterion_id in by_id:
            errors.append(f"duplicate criterion {criterion_id}")
            continue
        by_id[criterion_id] = criterion

    missing = [criterion_id for criterion_id in REQUIRED_CRITERIA if criterion_id not in by_id]
    unexpected = [criterion_id for criterion_id in by_id if criterion_id not in REQUIRED_CRITERIA]
    errors.extend(f"missing criterion {criterion_id}" for criterion_id in missing)
    errors.extend(f"unexpected criterion {criterion_id}" for criterion_id in unexpected)

    production_probability_claim = bool(manifest.get("probabilistic_production_claim", False))

    paper_policy = manifest.get("paper_shadow")
    if not isinstance(paper_policy, dict):
        paper_policy = {}
        errors.append("paper_shadow must be an object")
    required_paper = paper_policy.get("required_outcomes", 100)
    if not isinstance(required_paper, int) or isinstance(required_paper, bool) or required_paper < 100:
        errors.append("paper_shadow.required_outcomes must be an integer >= 100")
        required_paper = 100
    records_relative = paper_policy.get("records_path", "")
    if not isinstance(records_relative, str):
        errors.append("paper_shadow.records_path must be a string")
        records_relative = ""
    paper_count = count_valid_paper_shadow_records(root / records_relative) if records_relative else 0

    for criterion_id in REQUIRED_CRITERIA:
        criterion = by_id.get(criterion_id)
        if criterion is None:
            continue

        status = criterion.get("status")
        if status not in VALID_STATUSES:
            errors.append(f"{criterion_id}: invalid status {status!r}")
            continue

        evidence_class = criterion.get("evidence_class")
        if evidence_class not in VALID_EVIDENCE_CLASSES:
            errors.append(f"{criterion_id}: invalid evidence_class {evidence_class!r}")

        refs = criterion.get("evidence_refs", [])
        if not isinstance(refs, list):
            errors.append(f"{criterion_id}: evidence_refs must be a list")
            refs = []
        _check_repo_refs(refs, root, errors, criterion_id)

        if status == "SATISFIED" and not refs:
            errors.append(f"{criterion_id}: SATISFIED requires evidence_refs")

        if status == "NOT_APPLICABLE":
            if criterion_id not in CONDITIONAL_NOT_APPLICABLE:
                errors.append(f"{criterion_id}: NOT_APPLICABLE is not permitted")
                blockers.append(criterion_id)
                continue
            if criterion_id == "ML_CALIBRATION_IF_PROBABILISTIC" and production_probability_claim:
                blockers.append(criterion_id)
            else:
                not_applicable.append(criterion_id)
            continue

        if criterion_id in LIVE_EVIDENCE_CRITERIA and status == "SATISFIED":
            if evidence_class not in {"LIVE", "OPERATIONAL"}:
                errors.append(f"{criterion_id}: SATISFIED requires LIVE/OPERATIONAL evidence")
            if not _aware_iso8601(criterion.get("verified_at")):
                errors.append(f"{criterion_id}: SATISFIED requires timezone-aware verified_at")

        if criterion_id == PAPER_SHADOW_CRITERION:
            if status == "SATISFIED" and paper_count >= required_paper:
                satisfied.append(criterion_id)
            else:
                blockers.append(criterion_id)
            continue

        if status == "SATISFIED":
            satisfied.append(criterion_id)
        else:
            blockers.append(criterion_id)

    if errors:
        status = "NOT_GRADUATED"
    else:
        status = "GRADUATED" if not blockers else "NOT_GRADUATED"

    return GraduationReport(
        status=status,
        satisfied=tuple(satisfied),
        not_applicable=tuple(not_applicable),
        blockers=tuple(blockers),
        errors=tuple(errors),
        paper_shadow_valid_outcomes=paper_count,
        required_paper_shadow_outcomes=required_paper,
    )
