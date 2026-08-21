#!/usr/bin/env python3
"""Build the public Markdown report and charts from monthly JSON records."""

from __future__ import annotations

import json
import math
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MONTHLY_DIR = ROOT / "reports" / "monthly"
REPORT_PATH = ROOT / "REPORT.md"
CHARTS_DIR = ROOT / "assets" / "charts"

RESULT_STATUSES = {
    "improved",
    "stable",
    "regressed",
    "inconclusive",
    "insufficient_data",
    "failed",
}
REWARD_VALUE_FIELDS = (
    "mean",
    "median",
    "standard_deviation",
    "minimum",
    "maximum",
    "p25",
    "p75",
    "positive_rate",
)
KNOWN_CHARTS = {
    "reward-trend.svg",
    "reward-sample-count.svg",
    "reward-positive-rate.svg",
}


def _is_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _require_non_negative_int(value: Any, field: str, errors: list[str]) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        errors.append(f"{field} must be a non-negative integer")


def _validate_optional_non_negative_int(value: Any, field: str, errors: list[str]) -> None:
    if value is not None:
        _require_non_negative_int(value, field, errors)


def validate_record(data: Any, source: Path) -> list[str]:
    """Return human-readable validation errors for one monthly record."""
    prefix = source.name
    if not isinstance(data, dict):
        return [f"{prefix}: record must be a JSON object"]

    required = {
        "schema_version",
        "report_month",
        "system_revision",
        "status",
        "reward_definition",
        "reward",
    }
    allowed = required | {"model", "training_data", "notes"}
    errors: list[str] = []

    missing = sorted(required - set(data))
    unknown = sorted(set(data) - allowed)
    if missing:
        errors.append(f"{prefix}: missing fields: {', '.join(missing)}")
    if unknown:
        errors.append(f"{prefix}: unknown fields: {', '.join(unknown)}")
    if missing:
        return errors

    if data["schema_version"] != "1.0":
        errors.append(f"{prefix}: schema_version must be 1.0")
    expected_month = source.stem
    if data["report_month"] != expected_month:
        errors.append(f"{prefix}: report_month must match filename ({expected_month})")
    if not isinstance(data["report_month"], str) or not re.fullmatch(
        r"\d{4}-(0[1-9]|1[0-2])", data["report_month"]
    ):
        errors.append(f"{prefix}: report_month must use YYYY-MM with a valid month")
    if not isinstance(data["system_revision"], str) or not data["system_revision"].strip():
        errors.append(f"{prefix}: system_revision must be a non-empty string")
    if data["status"] not in RESULT_STATUSES:
        errors.append(f"{prefix}: invalid status {data['status']!r}")

    definition = data["reward_definition"]
    definition_fields = {"version", "higher_is_better", "comparable_group"}
    if not isinstance(definition, dict) or set(definition) != definition_fields:
        errors.append(f"{prefix}: reward_definition fields must be {sorted(definition_fields)}")
    else:
        for field in ("version", "comparable_group"):
            if not isinstance(definition[field], str) or not definition[field].strip():
                errors.append(f"{prefix}: reward_definition.{field} must be a non-empty string")
        if not isinstance(definition["higher_is_better"], bool):
            errors.append(f"{prefix}: reward_definition.higher_is_better must be boolean")

    reward = data["reward"]
    reward_fields = {"sample_count", *REWARD_VALUE_FIELDS}
    if not isinstance(reward, dict) or set(reward) != reward_fields:
        errors.append(f"{prefix}: reward fields must be {sorted(reward_fields)}")
    else:
        _require_non_negative_int(reward["sample_count"], "reward.sample_count", errors)
        for field in REWARD_VALUE_FIELDS:
            value = reward[field]
            if value is not None and not _is_number(value):
                errors.append(f"{prefix}: reward.{field} must be a finite number or null")
        positive_rate = reward["positive_rate"]
        if _is_number(positive_rate) and not 0 <= float(positive_rate) <= 1:
            errors.append(f"{prefix}: reward.positive_rate must be between 0 and 1")
        sample_count = reward["sample_count"]
        if isinstance(sample_count, int) and not isinstance(sample_count, bool):
            present_values = [reward[field] for field in REWARD_VALUE_FIELDS]
            if sample_count == 0 and any(value is not None for value in present_values):
                errors.append(f"{prefix}: Reward statistics must be null when sample_count is 0")
            if sample_count > 0 and any(value is None for value in present_values):
                errors.append(f"{prefix}: all Reward statistics are required when sample_count is positive")
        if _is_number(reward["standard_deviation"]) and reward["standard_deviation"] < 0:
            errors.append(f"{prefix}: reward.standard_deviation must be non-negative")
        ordered_values = [
            reward["minimum"],
            reward["p25"],
            reward["median"],
            reward["p75"],
            reward["maximum"],
        ]
        if all(_is_number(value) for value in ordered_values):
            if ordered_values != sorted(ordered_values):
                errors.append(f"{prefix}: reward summary must satisfy minimum <= p25 <= median <= p75 <= maximum")

    model = data.get("model")
    if model is not None:
        model_fields = {"public_revision", "parameter_count", "trainable_parameter_count"}
        if not isinstance(model, dict) or set(model) != model_fields:
            errors.append(f"{prefix}: model fields must be {sorted(model_fields)}")
        else:
            public_revision = model["public_revision"]
            if public_revision is not None and (
                not isinstance(public_revision, str) or not public_revision.strip()
            ):
                errors.append(f"{prefix}: model.public_revision must be a non-empty string or null")
            _validate_optional_non_negative_int(model["parameter_count"], "model.parameter_count", errors)
            _validate_optional_non_negative_int(
                model["trainable_parameter_count"], "model.trainable_parameter_count", errors
            )
            if (
                isinstance(model["parameter_count"], int)
                and isinstance(model["trainable_parameter_count"], int)
                and model["trainable_parameter_count"] > model["parameter_count"]
            ):
                errors.append(f"{prefix}: trainable parameters cannot exceed total parameters")

    training_data = data.get("training_data")
    if training_data is not None:
        training_fields = {"sample_count", "size_bytes"}
        if not isinstance(training_data, dict) or set(training_data) != training_fields:
            errors.append(f"{prefix}: training_data fields must be {sorted(training_fields)}")
        else:
            _validate_optional_non_negative_int(
                training_data["sample_count"], "training_data.sample_count", errors
            )
            _validate_optional_non_negative_int(
                training_data["size_bytes"], "training_data.size_bytes", errors
            )

    notes = data.get("notes")
    if notes is not None and (
        not isinstance(notes, list) or any(not isinstance(note, str) for note in notes)
    ):
        errors.append(f"{prefix}: notes must be a list of strings")
    return errors


def load_records() -> list[dict[str, Any]]:
    MONTHLY_DIR.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    for path in sorted(MONTHLY_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path.name}: cannot read JSON: {exc}")
            continue
        errors.extend(validate_record(data, path))
        records.append(data)
    if errors:
        raise ValueError("Invalid monthly research data:\n- " + "\n- ".join(errors))
    records.sort(key=lambda item: item["report_month"])
    group_definitions: dict[str, tuple[str, bool]] = {}
    for record in records:
        definition = record["reward_definition"]
        group = definition["comparable_group"]
        signature = (definition["version"], definition["higher_is_better"])
        previous = group_definitions.setdefault(group, signature)
        if previous != signature:
            raise ValueError(
                f"Comparable group {group!r} uses inconsistent Reward definitions: "
                f"{previous!r} and {signature!r}"
            )
    return records


def _format_number(value: Any, digits: int = 4) -> str:
    if not _is_number(value):
        return "—"
    return f"{float(value):.{digits}f}"


def _format_percent(value: Any) -> str:
    if not _is_number(value):
        return "—"
    return f"{float(value) * 100:.1f}%"


def _format_integer(value: Any) -> str:
    if not isinstance(value, int) or isinstance(value, bool):
        return "—"
    return f"{value:,}"


def _format_bytes(value: Any) -> str:
    if not isinstance(value, int) or isinstance(value, bool):
        return "—"
    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024 or unit == "TiB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return "—"


def _mean_delta(records: list[dict[str, Any]], index: int) -> str:
    current = records[index]
    current_mean = current["reward"]["mean"]
    current_group = current["reward_definition"]["comparable_group"]
    if not _is_number(current_mean):
        return "—"
    for previous in reversed(records[:index]):
        if previous["reward_definition"]["comparable_group"] != current_group:
            continue
        previous_mean = previous["reward"]["mean"]
        if _is_number(previous_mean):
            return f"{float(current_mean) - float(previous_mean):+.4f}"
    return "—"


def build_charts(records: list[dict[str, Any]]) -> set[str]:
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    if not records:
        for name in KNOWN_CHARTS:
            path = CHARTS_DIR / name
            if path.exists():
                path.unlink()
        return set()

    renderer = ROOT / "scripts" / "render_charts.mjs"
    try:
        result = subprocess.run(
            ["node", str(renderer), str(CHARTS_DIR)],
            input=json.dumps(records, ensure_ascii=False),
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("Node.js is required to render ECharts SVG files.") from exc

    if result.returncode != 0:
        detail = result.stderr.strip() or "unknown ECharts renderer error"
        raise RuntimeError(f"Chart rendering failed. Run `npm install` first.\n{detail}")
    try:
        generated = set(json.loads(result.stdout))
    except (json.JSONDecodeError, TypeError) as exc:
        raise RuntimeError("ECharts renderer returned an invalid result.") from exc
    if not generated <= KNOWN_CHARTS:
        raise RuntimeError(f"ECharts renderer returned unexpected files: {sorted(generated - KNOWN_CHARTS)}")

    for name in KNOWN_CHARTS - generated:
        path = CHARTS_DIR / name
        if path.exists():
            path.unlink()
    return generated


def _weighted_reward_summary(records: list[dict[str, Any]]) -> tuple[int, float | None, str | None]:
    if not records:
        return 0, None, None
    group = records[-1]["reward_definition"]["comparable_group"]
    relevant = [
        record
        for record in records
        if record["reward_definition"]["comparable_group"] == group
        and record["reward"]["sample_count"] > 0
        and _is_number(record["reward"]["mean"])
    ]
    total_count = sum(record["reward"]["sample_count"] for record in relevant)
    if total_count == 0:
        return 0, None, group
    weighted_mean = sum(
        record["reward"]["sample_count"] * float(record["reward"]["mean"])
        for record in relevant
    ) / total_count
    return total_count, weighted_mean, group


def build_markdown(records: list[dict[str, Any]], charts: set[str]) -> str:
    lines = [
        "# Stock Decision Research Report",
        "",
        "> Generated from monthly JSON records. Do not edit this file manually.",
        "",
    ]
    if not records:
        lines.extend([
            "## Status",
            "",
            "No monthly research records have been added yet.",
            "",
        ])
        return "\n".join(lines)

    latest = records[-1]
    total_count, weighted_mean, group = _weighted_reward_summary(records)
    lines.extend([
        "## Latest status",
        "",
        f"- Latest month: `{latest['report_month']}`",
        f"- System revision: `{latest['system_revision']}`",
        f"- Result status: `{latest['status']}`",
        f"- Reward definition: `{latest['reward_definition']['version']}`",
        f"- Comparable group: `{latest['reward_definition']['comparable_group']}`",
        f"- Latest Reward samples: {_format_integer(latest['reward']['sample_count'])}",
        f"- Latest mean Reward: {_format_number(latest['reward']['mean'])}",
        "",
        "## Comparable-history summary",
        "",
        f"The current comparison group is `{group}`. Statistics from other Reward definitions are not merged into this summary.",
        "",
        f"- Comparable Reward samples: {_format_integer(total_count)}",
        f"- Sample-weighted mean Reward: {_format_number(weighted_mean)}",
        "",
    ])

    if "reward-trend.svg" in charts:
        lines.extend([
            "## Reward trend",
            "",
            "![Monthly Reward trend](assets/charts/reward-trend.svg)",
            "",
        ])
    if "reward-sample-count.svg" in charts:
        lines.extend([
            "## Evaluation volume",
            "",
            "![Monthly Reward sample count](assets/charts/reward-sample-count.svg)",
            "",
        ])
    if "reward-positive-rate.svg" in charts:
        lines.extend([
            "## Positive Reward rate",
            "",
            "![Monthly positive Reward rate](assets/charts/reward-positive-rate.svg)",
            "",
        ])

    lines.extend([
        "## Monthly Reward table",
        "",
        "| Month | Status | Reward group | Samples | Mean | Median | P25 | P75 | Positive | Δ Mean |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for index, record in enumerate(records):
        reward = record["reward"]
        lines.append(
            "| "
            + " | ".join([
                record["report_month"],
                record["status"],
                record["reward_definition"]["comparable_group"],
                _format_integer(reward["sample_count"]),
                _format_number(reward["mean"]),
                _format_number(reward["median"]),
                _format_number(reward["p25"]),
                _format_number(reward["p75"]),
                _format_percent(reward["positive_rate"]),
                _mean_delta(records, index),
            ])
            + " |"
        )
    lines.append("")

    if any(record.get("model") or record.get("training_data") for record in records):
        lines.extend([
            "## Model and training-data information",
            "",
            "| Month | Model revision | Parameters | Trainable parameters | Training samples | Training data size |",
            "|---|---|---:|---:|---:|---:|",
        ])
        for record in records:
            model = record.get("model") or {}
            training = record.get("training_data") or {}
            lines.append(
                "| "
                + " | ".join([
                    record["report_month"],
                    model.get("public_revision") or "—",
                    _format_integer(model.get("parameter_count")),
                    _format_integer(model.get("trainable_parameter_count")),
                    _format_integer(training.get("sample_count")),
                    _format_bytes(training.get("size_bytes")),
                ])
                + " |"
            )
        lines.append("")

    noted_records = [record for record in records if record.get("notes")]
    if noted_records:
        lines.extend(["## Monthly notes", ""])
        for record in noted_records:
            lines.append(f"### {record['report_month']}")
            lines.append("")
            for note in record["notes"]:
                lines.append(f"- {note}")
            lines.append("")

    lines.extend([
        "## Interpretation boundary",
        "",
        "Reward comparisons are valid only within the same comparison group. Sample volume, Reward-definition changes, and missing values must be considered before interpreting a trend. Historical simulation is not actual execution or evidence of future profitability.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    try:
        records = load_records()
        charts = build_charts(records)
        REPORT_PATH.write_text(build_markdown(records, charts), encoding="utf-8")
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Report generation failed: {exc}", file=sys.stderr)
        return 1
    print(f"Generated {REPORT_PATH.relative_to(ROOT)} from {len(records)} monthly record(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
