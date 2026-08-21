# Stock Decision Research

An independent research project exploring how an AI-assisted system can support observe, enter, hold, and exit decisions across trading days.

> 這是一個個人股票決策系統研究專案，聚焦跨交易日的觀察、進場、持有與退出決策。此 repository 保存可公開的月度彙總資料，並以圖表和表格呈現長期研究變化。

## Current status

- Public revision: `research-v0.1`
- Project stage: active research prototype
- Primary analysis: monthly Reward change
- Historical evaluation: in progress
- Live deployment: not supported
- Profitability: not established

## Research view

```text
Observe -> Enter -> Hold -> Exit
```

The current public analysis focuses on how aggregated Reward changes over time. Future reports may include public model-scale and training-data information when those fields are ready for safe publication.

## Research report

- [Generated research report](REPORT.md)
- [Monthly data format](reports/README.md)

Monthly JSON records are the source of truth. The report and ECharts SVG charts are generated from those records with:

```bash
npm install
python3 scripts/build_report.py
```

## Repository structure

```text
reports/monthly/       Sanitized monthly JSON records (source of truth)
scripts/               Markdown builder and ECharts SVG renderer
assets/charts/         Generated SVG charts displayed by REPORT.md
REPORT.md              Generated complete research report
reports/README.md      Monthly input format and comparison rules
```

`AGENTS.md` and `.private/` are intentionally excluded from Git because they contain local working rules and planning notes.

## Public boundary

This repository may contain aggregated Reward statistics, public system revisions, model parameter counts, and training-data volume summaries. It does not publish raw market data, individual stock decisions, exact strategy rules, model weights, credentials, or live-order capabilities.

Historical simulation is not actual execution. This project is provided for research and engineering discussion only and is not financial advice or a claim of future profitability.
