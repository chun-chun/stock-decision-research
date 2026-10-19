#!/usr/bin/env python3
"""Build the public Markdown report from sanitized aggregate data on stdin."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "REPORT.md"
CHARTS_DIR = ROOT / "assets" / "charts"
PREVIEW_ROOT = ROOT / ".private" / "report-preview"

RESULT_STATUSES = {"validated", "skipped", "partial", "failed"}
BASE_CHARTS = {
    "monthly-net-profit.svg",
    "capital-usage.svg",
    "transaction-cost.svg",
}
KNOWN_CHARTS = BASE_CHARTS
MANAGED_CHARTS = KNOWN_CHARTS | {
    "evaluation-volume.svg",
    "task-days.svg",
    "trade-status.svg",
    "financial-outcome.svg",
    "reward-trend.svg",
    "reward-sample-count.svg",
    "reward-positive-rate.svg",
    "task-completion.svg",
    "buy-probability-stability.svg",
    "sell-probability-stability.svg",
}


def _is_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def validate_payload(payload: Any) -> list[str]:
    """Return validation errors for the public, aggregate-only report contract."""
    if not isinstance(payload, dict):
        return ["report payload must be an object"]
    required = {
        "schema_version",
        "generated_at",
        "public_revision",
        "validation_protocol",
        "period",
        "months",
        "warnings",
    }
    errors: list[str] = []
    missing = sorted(required - set(payload))
    unknown = sorted(set(payload) - required)
    if missing:
        errors.append(f"missing fields: {', '.join(missing)}")
    if unknown:
        errors.append(f"unknown fields: {', '.join(unknown)}")
    if missing:
        return errors
    if payload["schema_version"] != "1.2":
        errors.append("schema_version must be 1.2")
    if not isinstance(payload["public_revision"], str) or not payload["public_revision"].strip():
        errors.append("public_revision must be a non-empty string")
    if not isinstance(payload["generated_at"], str) or not payload["generated_at"].strip():
        errors.append("generated_at must be a non-empty string")
    if (
        not isinstance(payload["validation_protocol"], str)
        or not payload["validation_protocol"].strip()
    ):
        errors.append("validation_protocol must be a non-empty string")

    period = payload["period"]
    if not isinstance(period, dict) or set(period) != {
        "start_month",
        "end_month",
        "month_count",
    }:
        errors.append("period fields are invalid")

    months = payload["months"]
    if not isinstance(months, list) or not months:
        errors.append("months must be a non-empty list")
        return errors
    required_month_fields = {
        "month",
        "status",
        "validation_days",
        "evaluation_count",
        "total_transaction_cost",
        "max_order_transaction_cost",
        "realized_net_profit",
        "buy_notional",
        "max_position_capital",
    }
    seen_months = set()
    for index, item in enumerate(months):
        prefix = f"months[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} fields are invalid")
            continue
        item_fields = set(item)
        month = item.get("month")
        if not isinstance(month, str) or len(month) != 7 or month[4] != "-":
            errors.append(f"{prefix}.month must use YYYY-MM")
        elif month in seen_months:
            errors.append(f"duplicate month: {month}")
        else:
            seen_months.add(month)
        if item_fields != required_month_fields:
            errors.append(f"{prefix} fields are invalid")
            continue
        if item["status"] not in RESULT_STATUSES:
            errors.append(f"{prefix}.status is invalid")
        for field in (
            "validation_days",
            "evaluation_count",
        ):
            value = item[field]
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                errors.append(f"{prefix}.{field} must be a non-negative integer")
        for field in (
            "total_transaction_cost",
            "max_order_transaction_cost",
            "realized_net_profit",
            "max_position_capital",
            "buy_notional",
        ):
            if item[field] is not None and not _is_number(item[field]):
                errors.append(f"{prefix}.{field} must be finite or null")

    sorted_months = sorted(seen_months)
    if isinstance(period, dict) and sorted_months:
        if period.get("start_month") != sorted_months[0]:
            errors.append("period.start_month does not match months")
        if period.get("end_month") != sorted_months[-1]:
            errors.append("period.end_month does not match months")
        if period.get("month_count") != len(months):
            errors.append("period.month_count does not match months")
    if not isinstance(payload["warnings"], list) or any(
        not isinstance(item, str) for item in payload["warnings"]
    ):
        errors.append("warnings must be a list of strings")
    return errors


def build_charts(
    payload: dict[str, Any],
    *,
    charts_dir: Path = CHARTS_DIR,
) -> set[str]:
    charts_dir.parent.mkdir(parents=True, exist_ok=True)
    renderer = ROOT / "scripts" / "render_charts.mjs"
    with tempfile.TemporaryDirectory(
        prefix=".validation-charts-",
        dir=charts_dir.parent,
    ) as temporary_directory:
        temporary_root = Path(temporary_directory)
        try:
            result = subprocess.run(
                ["node", str(renderer), str(temporary_root)],
                input=json.dumps(payload, ensure_ascii=True, allow_nan=False),
                text=True,
                capture_output=True,
                check=False,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("Node.js is required to render the report charts.") from exc
        if result.returncode != 0:
            detail = result.stderr.strip() or "unknown ECharts renderer error"
            raise RuntimeError(
                f"Chart rendering failed. Run `npm install` first.\n{detail}"
            )
        try:
            generated = set(json.loads(result.stdout))
        except (json.JSONDecodeError, TypeError) as exc:
            raise RuntimeError("ECharts renderer returned an invalid result.") from exc
        expected_charts = BASE_CHARTS
        if generated != expected_charts:
            raise RuntimeError(
                "ECharts renderer returned an incomplete or unexpected file set: "
                f"{sorted(generated)}"
            )
        missing_files = sorted(
            name for name in generated if not (temporary_root / name).is_file()
        )
        if missing_files:
            raise RuntimeError(
                f"ECharts renderer did not write declared files: {missing_files}"
            )
        charts_dir.mkdir(parents=True, exist_ok=True)
        for name in sorted(generated):
            os.replace(temporary_root / name, charts_dir / name)

    for name in MANAGED_CHARTS - generated:
        path = charts_dir / name
        if path.exists():
            path.unlink()
    return generated


def _format_integer(value: Any) -> str:
    return "—" if not isinstance(value, int) or isinstance(value, bool) else f"{value:,}"


def _format_money(value: Any) -> str:
    return "—" if not _is_number(value) else f"TWD {float(value):,.0f}"


def _complete_sum(values: list[Any]) -> float | None:
    if not values or any(not _is_number(value) for value in values):
        return None
    return sum(float(value) for value in values)


def _available_max(values: list[Any]) -> float | None:
    available = [float(value) for value in values if _is_number(value)]
    return max(available) if available else None


def build_markdown(
    payload: dict[str, Any],
    charts: set[str],
    *,
    preview: bool = False,
) -> str:
    months = sorted(payload["months"], key=lambda item: item["month"])
    single_month = len(months) == 1
    period = payload["period"]
    validation_days = sum(item["validation_days"] for item in months)
    evaluation_count = sum(item["evaluation_count"] for item in months)
    net_profit = _complete_sum([item["realized_net_profit"] for item in months])
    transaction_cost = _complete_sum(
        [item["total_transaction_cost"] for item in months]
    )
    buy_notional = _complete_sum([item["buy_notional"] for item in months])
    peak_capital = _available_max(
        [item["max_position_capital"] for item in months]
    )
    max_order_cost = _available_max(
        [item["max_order_transaction_cost"] for item in months]
    )
    heading = (
        "# Layout Preview: Monthly Research Report"
        if preview
        else "# Stock Decision Research Report"
    )
    lines = [
        heading,
        "",
    ]
    if preview:
        lines.extend([
            "> **LAYOUT PREVIEW / SYNTHETIC DATA.** Values on this page are invented "
            "for visual review and are not research evidence.",
            "",
        ])
    lines.extend([
        "> Historical-simulation aggregates only. This is not actual execution, "
        "financial advice, or evidence of future profitability.",
        "",
        "## This Month" if single_month else "## Research Snapshot",
        "",
        "| Period | Public revision | Protocol | Months | Validation days | Evaluations |",
        "|---|---|---|---:|---:|---:|",
        "| "
        + " | ".join([
            f"{period['start_month']} to {period['end_month']}",
            f"`{payload['public_revision']}`",
            f"`{payload['validation_protocol']}`",
            _format_integer(period["month_count"]),
            _format_integer(validation_days),
            _format_integer(evaluation_count),
        ])
        + " |",
        "",
        "| Net result after costs | Total purchase value | Recorded peak position capital | Total transaction costs | Largest single-order cost |",
        "|---:|---:|---:|---:|---:|",
        "| "
        + " | ".join([
            _format_money(net_profit),
            _format_money(buy_notional),
            _format_money(peak_capital),
            _format_money(transaction_cost),
            _format_money(max_order_cost),
        ])
        + " |",
        "",
    ])

    lines.extend([
        "All monetary amounts are in TWD. Total purchase value is the sum of purchases "
        "during the period; it is not starting capital. Recorded peak position capital "
        "is the maximum capital value supplied by the evaluation, not an assumed "
        "portfolio-wide funding requirement. Total costs and the largest single-order "
        "cost are distinct measures. Net result already includes recorded costs; do "
        "not subtract them again.",
        "",
    ])
    if single_month:
        lines.extend(["This first monthly observation does not establish a trend. "
                      "The report focuses on the month's result, costs, and research observations.", ""])
    lines.extend(["## Monthly Research Notes", ""])
    for item in months:
        lines.extend([
            f"### {item['month']}", "",
            f"- **Finding:** Recorded net result after costs: {_format_money(item['realized_net_profit'])}; "
            f"recorded transaction costs: {_format_money(item['total_transaction_cost'])}.",
            f"- **Limitation:** This month's summary contains {item['evaluation_count']:,} evaluations "
            f"with status `{item['status']}`. These aggregates alone do not establish sample "
            "representativeness or persistent performance. See the report limitations for context.",
            "- **Next step:** Compare the next available month under a compatible revision and "
            "protocol, tracking net result, costs, and recorded capital together.", "",
        ])

    chart_prefix = "assets/charts"
    chart_sections = [
        (
            "monthly-net-profit.svg",
            "## 1. Monthly Net Result",
            "Net result after recorded costs for this month."
            if single_month else "Compare monthly net results after recorded costs across compatible months.",
            "Monthly net result" if single_month else "Monthly net result and cumulative net result",
        ),
        (
            "capital-usage.svg",
            "## 2. Monthly Capital Usage",
            "Total purchase value and recorded peak position capital, shown on the same TWD scale. "
            "Purchase value measures activity, not starting capital.",
            "Total purchase value and recorded peak position capital in TWD",
        ),
        (
            "transaction-cost.svg",
            "## 3. Monthly Transaction Costs",
            "How much did recorded transaction costs consume, and how large was the "
            "largest single-order cost each month?",
            "Monthly total transaction costs and maximum single-order cost",
        ),
    ]
    for chart_name, section_title, description, alt_text in chart_sections:
        if chart_name not in charts:
            continue
        lines.extend([
            section_title,
            "",
            description,
            "",
            f"![{alt_text}]({chart_prefix}/{chart_name})",
            "",
        ])

    lines.extend([
        "## Monthly Ledger",
        "",
        "| Month | Status | Days | Evaluations | Net result after costs | Total purchase value | Recorded peak position capital | Total costs | Largest single-order cost |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for item in months:
        row = [
            item["month"],
            item["status"],
            _format_integer(item["validation_days"]),
            _format_integer(item["evaluation_count"]),
            _format_money(item["realized_net_profit"]),
            _format_money(item["buy_notional"]),
            _format_money(item["max_position_capital"]),
            _format_money(item["total_transaction_cost"]),
            _format_money(item["max_order_transaction_cost"]),
        ]
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    if payload["warnings"]:
        lines.extend(["## Limitations", ""])
        lines.extend(f"- {warning}" for warning in payload["warnings"])
        lines.append("")
    lines.extend([
        "## Interpretation boundary",
        "",
        "Net result, notional, capital, and transaction costs are historical-simulation "
        "measurements. Month-to-month comparisons are meaningful only when the public "
        "revision and validation protocol remain comparable. Missing values are shown "
        "as unavailable rather than zero.",
        "",
    ])
    return "\n".join(lines).rstrip()


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, text=True
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read one sanitized aggregate report payload from standard input.",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help=(
            "Write an ignored layout preview under .private/report-preview instead "
            "of replacing the formal report."
        ),
    )
    parser.add_argument("--output-subdir", help="Managed local research series directory.")
    args = parser.parse_args(argv)
    if not args.stdin:
        parser.error("--stdin is required; public monthly JSON files are not used.")
    try:
        payload = json.load(sys.stdin)
        errors = validate_payload(payload)
        if errors:
            raise ValueError("Invalid research report payload:\n- " + "\n- ".join(errors))
        if args.output_subdir and (args.preview or re.fullmatch(r"reports/(intraday|multi-day)-r[1-9][0-9]*", args.output_subdir) is None):
            raise ValueError("Invalid research series output directory")
        output_root = ROOT / args.output_subdir if args.output_subdir else ROOT
        if not output_root.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError("Research output must remain inside this repository")
        report_path = PREVIEW_ROOT / "REPORT.md" if args.preview else output_root / "REPORT.md"
        charts_dir = (
            PREVIEW_ROOT / "assets" / "charts" if args.preview else output_root / "assets" / "charts"
        )
        charts = build_charts(payload, charts_dir=charts_dir)
        _atomic_write(
            report_path,
            build_markdown(payload, charts, preview=args.preview),
        )
        if args.output_subdir:
            lines = ["# Stock Decision Research", "", "> Local historical-simulation summaries. Not actual execution or evidence of future profitability.", "", "## Research Series", "", "| Series | Report |", "| --- | --- |"]
            for path in sorted((ROOT / "reports").glob("*/REPORT.md")):
                series = path.parent.name
                if re.fullmatch(r"(intraday|multi-day)-r[1-9][0-9]*", series):
                    lines.append(f"| {series} | [Charts and monthly tables]({path.relative_to(ROOT).as_posix()}) |")
            lines.extend(["", "Each series uses a separate declared configuration revision. Do not combine overlapping months across series.", "", "Only explicitly selected, complete decision-validation months are included. Omitted months are not zero-profit months.", "", "Same-series monthly corrections replace the selected month; source revision history remains in the private implementation.", "", "Generated locally; no automatic commit, push, or publication.", ""])
            if REPORT_PATH.exists():
                from datetime import datetime
                archive = ROOT / ".private" / "report-history" / (datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".md")
                _atomic_write(archive, REPORT_PATH.read_text(encoding="utf-8"))
            _atomic_write(REPORT_PATH, "\n".join(lines))
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"Report generation failed: {exc}", file=sys.stderr)
        return 1
    print(
        f"Generated {report_path.relative_to(ROOT)} from "
        f"{len(payload['months'])} sanitized month(s)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
