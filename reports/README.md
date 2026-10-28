# Report Input Boundary

`REPORT.md` and `assets/charts/*.svg` are generated from sanitized aggregate data supplied by the private validation project through standard input.

This repository does not store a monthly JSON source of truth. Canonical validation results remain private; the public renderer receives only an in-memory allowlisted schema `1.2` payload and writes human-readable report artifacts.

## Allowed monthly fields

- Month and public result status
- Validation-day and aggregate evaluation counts
- Aggregate historical-simulation net result, gross buy notional, transaction costs, and peak position capital
- Public revision, validation-protocol revision, and report limitations

## Prohibited fields

- Stock identifiers, task identifiers, source/task/order timestamps, or individual decisions; only the public report generation time is allowed
- Task lifecycle outcomes, action/fill details, decision probabilities, or Reward
- Internal model names, paths, run ids, source filenames, or logs
- Exact features, thresholds, labels, Reward formula, architecture, or strategy rules
- Raw market data, model weights, broker details, credentials, or live-order data

## Comparison rules

See [Research Reporting Workflow](WORKFLOW.md) for the monthly-first presentation. Each monthly entry includes Finding, Limitation, and Next step. Single-month charts omit the cumulative line. All money is labeled TWD; total purchase value, recorded peak position capital, total costs, and largest single-order cost remain distinct. Net result is already after recorded costs.

- A month is the primary trend unit.
- Validation and evaluation counts are summed, financial flows are summed, and capital or single-order maxima remain maxima.
- Missing data is shown as unavailable, never converted to zero.
- Month values must be real calendar months in `YYYY-MM` form, and validation-day counts cannot exceed the number of calendar days in that month.
- Transaction costs, purchase value, and recorded peak position capital must be non-negative when available. The largest single-order cost cannot exceed total transaction costs.
- Periods spanning multiple internal revisions carry an explicit warning and are not described as one unchanged policy.
- Historical simulation is not actual execution or evidence of future profitability.

The renderer is normally invoked by the private exporter. It requires a sanitized payload on standard input:

```bash
python3 scripts/build_report.py --stdin
```

For layout review with non-evidence data, add `--preview`. This writes only to the ignored `.private/report-preview/` directory and never replaces the formal report.

Every generated Markdown file and SVG must receive a semantic confidentiality review before commit or publication.
Charts are rendered in a temporary directory and replace the managed SVG set only after the renderer returns every expected file.

## Optional Local Monthly Sync

The private monthly-validation page has an explicit opt-in switch. Complete decision-only months may be exported; shortened windows, missing results, or unfinished tasks are not automatically exported. Negative months remain eligible. No automatic commit, push, or publication occurs.

`build_report.py --stdin --output-subdir reports/intraday-r1` (or a multi-day series) writes independently rendered Markdown/SVG under that series. The root report becomes a generated series index. Declared configuration revisions remain separate; they are not proof that weight files or market samples are identical. Prior root indexes are retained privately. Only aggregate allowlisted input crosses the boundary; private source selection and correction records stay outside this repository.
