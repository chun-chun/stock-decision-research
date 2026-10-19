# Stock Decision Research

An independent research project exploring how an AI-assisted system can support observe, enter, hold, and exit decisions across trading days.

> 這是一個個人股票決策系統研究專案，聚焦跨交易日的觀察、進場、持有與退出決策。此 repository 只保存可公開的彙總報告與圖表，不保存內部驗證資料。

## Current status

- Public revision: `research-v0.1`
- Project stage: active research prototype
- Primary analysis: monthly net result, capital usage, and transaction costs
- Historical evaluation: in progress
- Live deployment: not supported
- Profitability: not established

## Research view

```text
Observe -> Enter -> Hold -> Exit
```

## Research report

- [Generated research report](REPORT.md)
- [Report input and publication boundary](reports/README.md)

The private research system keeps canonical monthly validation results. Its exporter aggregates selected months in memory, removes private fields, and sends only a sanitized report payload to this repository's renderer. The renderer writes a Markdown summary and three static monthly charts:

```text
REPORT.md
assets/charts/*.svg
```

No copied monthly JSON or other intermediate data file is committed here. The public view intentionally uses only monthly coverage and financial aggregates: net result, gross buy notional, peak position capital, and transaction costs. Task outcomes, decisions, confidence values, Reward, and internal revision names never cross the public boundary.

## Repository structure

```text
scripts/               Markdown builder and ECharts SVG renderer
assets/charts/         Generated SVG charts displayed by REPORT.md
REPORT.md              Generated research report
reports/README.md      Input boundary and comparison rules
```

`AGENTS.md` and `.private/` are intentionally excluded from Git because they contain local working rules and planning notes.

## Public boundary

This repository may contain validation coverage and aggregate historical-simulation result, capital, and cost statistics. It does not publish task outcomes, decision probabilities, Reward, raw market data, individual stock decisions, exact strategy rules, model weights, credentials, internal paths, or live-order capabilities.

Historical simulation is not actual execution. This project is provided for research and engineering discussion only and is not financial advice or a claim of future profitability.
