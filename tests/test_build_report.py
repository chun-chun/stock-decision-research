import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_report.py"
SPEC = importlib.util.spec_from_file_location("build_report", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
build_report = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_report)


def valid_payload():
    return {
        "schema_version": "1.2",
        "generated_at": "2026-10-28T00:00:00+08:00",
        "public_revision": "research-v0.1",
        "validation_protocol": "historical-simulation-draft",
        "period": {
            "start_month": "2026-09",
            "end_month": "2026-09",
            "month_count": 1,
        },
        "months": [
            {
                "month": "2026-09",
                "status": "validated",
                "validation_days": 21,
                "evaluation_count": 10,
                "total_transaction_cost": 8904,
                "max_order_transaction_cost": 3620,
                "realized_net_profit": -8904,
                "buy_notional": 1522000,
                "max_position_capital": 810153,
            }
        ],
        "warnings": [],
    }


class ValidatePayloadTests(unittest.TestCase):
    def test_accepts_current_public_payload(self):
        self.assertEqual(build_report.validate_payload(valid_payload()), [])

    def test_rejects_invalid_calendar_month(self):
        payload = valid_payload()
        payload["months"][0]["month"] = "2026-99"
        payload["period"]["start_month"] = "2026-99"
        payload["period"]["end_month"] = "2026-99"
        errors = build_report.validate_payload(payload)
        self.assertIn("months[0].month must use YYYY-MM", errors)

    def test_rejects_validation_days_beyond_calendar_month(self):
        payload = valid_payload()
        payload["months"][0]["validation_days"] = 31
        errors = build_report.validate_payload(payload)
        self.assertIn("months[0].validation_days exceeds the calendar month", errors)

    def test_allows_negative_net_result(self):
        payload = valid_payload()
        payload["months"][0]["realized_net_profit"] = -100
        self.assertEqual(build_report.validate_payload(payload), [])

    def test_rejects_negative_non_profit_money_fields(self):
        for field in (
            "total_transaction_cost",
            "max_order_transaction_cost",
            "buy_notional",
            "max_position_capital",
        ):
            with self.subTest(field=field):
                payload = valid_payload()
                payload["months"][0][field] = -1
                errors = build_report.validate_payload(payload)
                self.assertIn(f"months[0].{field} must be non-negative or null", errors)

    def test_rejects_single_order_cost_above_total_cost(self):
        payload = valid_payload()
        payload["months"][0]["total_transaction_cost"] = 100
        payload["months"][0]["max_order_transaction_cost"] = 101
        errors = build_report.validate_payload(payload)
        self.assertIn(
            "months[0].max_order_transaction_cost cannot exceed total_transaction_cost",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
