# Monthly Research Data

Each month is stored as one JSON file under `reports/monthly/`:

```text
reports/monthly/2026-08.json
reports/monthly/2026-09.json
```

These JSON files are the source of truth for the generated report and charts. Do not edit `REPORT.md` or generated charts by hand.

## Monthly record

```json
{
  "schema_version": "1.0",
  "report_month": "YYYY-MM",
  "system_revision": "research-v0.1",
  "status": "insufficient_data",
  "reward_definition": {
    "version": "reward-v1",
    "higher_is_better": true,
    "comparable_group": "reward-v1"
  },
  "reward": {
    "sample_count": 0,
    "mean": null,
    "median": null,
    "standard_deviation": null,
    "minimum": null,
    "maximum": null,
    "p25": null,
    "p75": null,
    "positive_rate": null
  },
  "model": {
    "public_revision": null,
    "parameter_count": null,
    "trainable_parameter_count": null
  },
  "training_data": {
    "sample_count": null,
    "size_bytes": null
  },
  "notes": []
}
```

## Rules

- `report_month` must match the filename.
- `reward.sample_count` is the number of observations represented by the Reward statistics.
- Missing values use `null`, not `0`.
- `positive_rate` uses the range `0` to `1`.
- Reward values are compared only within the same `comparable_group`.
- A change to the Reward meaning requires a new Reward version or comparison group.
- Model and training-data fields are optional analysis metadata; they must remain aggregated and safe to publish.
- Notes may explain monthly changes and limitations, but must not contain private strategy details or individual decisions.

Run `python scripts/build_report.py` after adding or changing a month.
