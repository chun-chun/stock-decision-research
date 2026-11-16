import importlib.util
import unittest
import tempfile
from copy import deepcopy
from unittest.mock import patch
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
    def test_missing_counts_remain_unavailable(self):
        payload = valid_payload()
        payload['months'][0]['validation_days'] = None
        payload['months'][0]['evaluation_count'] = None
        self.assertEqual(build_report.validate_payload(payload), [])
        self.assertIn('Recorded evaluation count: —', build_report.build_markdown(payload, set()))

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


class PublicationTests(unittest.TestCase):
    def test_single_month_add_month_and_replace_same_month(self):
        payload = valid_payload()
        payload['comparison_mode'] = 'monthly_only'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'README.md').write_text('# System\n\n## Results\n\nOld result\n\n## Next\n\nKeep this.\n')
            build_report.publish_report(payload, root, update_readme=True)
            self.assertNotIn('Cumulative net result', (root / 'assets/charts/monthly-net-profit.svg').read_text())
            second = dict(payload['months'][0], month='2026-10', realized_net_profit=-100)
            payload['months'].append(second)
            payload['period'].update(end_month='2026-10', month_count=2)
            build_report.publish_report(payload, root, update_readme=True)
            readme = (root / 'README.md').read_text()
            self.assertIn('**2026-10**', readme)
            self.assertIn('TWD -100', readme)
            self.assertIn('Keep this.', readme)
            report = (root / 'REPORT.md').read_text()
            self.assertEqual(report.count('**Finding:**'), 2)
            self.assertIn('## Latest Month — 2026-10', report)
            self.assertNotIn('Cumulative net result', (root / 'assets/charts/monthly-net-profit.svg').read_text())
            self.assertIn('TWD -100', (root / 'assets/charts/monthly-net-profit.svg').read_text().replace('-100', 'TWD -100'))
            payload['months'][1]['realized_net_profit'] = -200
            build_report.publish_report(payload, root, update_readme=True)
            report = (root / 'REPORT.md').read_text()
            self.assertEqual(report.count('| 2026-10 |'), 1)
            self.assertIn('Correction recorded', report)
            self.assertIn('TWD -200', (root / 'README.md').read_text())
            self.assertFalse(list(root.rglob('*.json')))
            self.assertFalse(list(root.rglob('*.html')))

    def test_renderer_failure_preserves_existing_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'README.md').write_text('## Results\n\nOld\n')
            (root / 'REPORT.md').write_text('Previous report\n')
            before = {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            with patch.object(build_report, 'build_charts', side_effect=RuntimeError('render failed')):
                with self.assertRaisesRegex(RuntimeError, 'render failed'):
                    build_report.publish_report(valid_payload(), root, update_readme=True)
            self.assertEqual(before, {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()})

    def test_write_failure_rolls_back_replaced_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'README.md').write_text('## Results\n\nOld\n')
            build_report.publish_report(valid_payload(), root, update_readme=True)
            before = {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            original = build_report._atomic_write
            failed = False
            def fail_readme_once(path, text):
                nonlocal failed
                if path.name == 'README.md' and not failed:
                    failed = True
                    raise OSError('write failed')
                original(path, text)
            payload = deepcopy(valid_payload())
            payload['months'][0]['realized_net_profit'] = -123
            with patch.object(build_report, '_atomic_write', side_effect=fail_readme_once):
                with self.assertRaisesRegex(OSError, 'write failed'):
                    build_report.publish_report(payload, root, update_readme=True)
            self.assertEqual(before, {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()})


if __name__ == "__main__":
    unittest.main()
