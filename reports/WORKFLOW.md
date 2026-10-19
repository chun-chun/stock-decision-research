# Research Reporting Workflow

Monthly validation is the primary research view while the evidence base is small. Each report presents the evaluation scope, aggregate historical-simulation results, charts, limitations, and short research observations. The overview provides a concise entry point.

As comparable months accumulate, the overall research summary becomes the primary view. It presents cross-month results, transaction costs, capital usage, and revision changes. Monthly validation reports remain supporting evidence for review and traceability. The transition depends on evidence volume and comparability; no fixed month-count threshold is defined yet.

## Local update flow

1. Complete validation and update its saved summary in the private research system.
2. When local research synchronization is enabled, read those saved results without rerunning the model.
3. Aggregate and allowlist public fields before passing them to the report builder.
4. Regenerate the selected monthly view and overall summary together.
5. Review the generated Markdown, charts, and proposed Git changes locally.
6. The owner decides when to commit and upload to GitHub. Report generation does not automatically commit or push.

Reprocessing a month replaces that month's selected result rather than appending a duplicate. Additional months extend the historical record. Corrections to published results must be explained and dated.

## Presentation and comparison

The first monthly report focuses on that month's net result, costs, and research observations. A single month has no cumulative trend line or claim of persistence. Additional months can support comparison charts; their existence alone does not determine when the overall summary becomes the primary view.

Every monthly entry includes **Finding / Limitation / Next step**. The builder supplies factual aggregate observations and a clearly stated follow-up direction; it does not infer causes or invent research conclusions from missing evidence.

Charts and tables use TWD explicitly. Total purchase value measures buying activity, not starting capital. Recorded peak position capital is the maximum supplied by the evaluation; it must not be described as portfolio-wide required funding without evidence. Total transaction costs and the largest single-order cost are distinct. Recorded costs are already included in net result. Capital and cost comparisons use a shared monetary axis.

- Use Markdown with static ECharts SVG charts and concise aggregate tables.
- Start with monthly net result, transaction costs, capital usage, and evaluation coverage.
- Keep per-task analysis and raw validation data private. Reward remains private until its meaning and publication boundary are explicitly reviewed.
- Group incompatible model revisions or evaluation protocols separately. Do not describe pooled results as one unchanged system.
- Keep negative, inconclusive, and insufficient-data outcomes visible and clearly labeled.
- Show unavailable measurements as unavailable, not zero.

The complete public-data boundary is documented in [Report Input Boundary](README.md). This workflow describes the intended reporting behavior; it does not assert that every integration step has been implemented or verified.
