#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import * as echarts from 'echarts';

const outputDir = process.argv[2];
if (!outputDir) {
  console.error('Usage: render_charts.mjs OUTPUT_DIR');
  process.exit(2);
}

let input = '';
for await (const chunk of process.stdin) input += chunk;
const payload = JSON.parse(input || '{}');
const months = Array.isArray(payload.months) ? payload.months : [];
months.sort((a, b) => a.month.localeCompare(b.month));
const singleMonth = months.length === 1;
fs.mkdirSync(outputDir, { recursive: true });

const colors = {
  background: '#fbf8f0',
  ink: '#183338',
  muted: '#617276',
  grid: '#d8dfda',
  cyan: '#078c9a',
  blue: '#426f86',
  green: '#3e8060',
  red: '#bc4d55',
  gold: '#cf9433',
  slate: '#829397',
};

const monthLabels = months.map((item) => item.month);
const toNumber = (value) => (
  typeof value === 'number' && Number.isFinite(value) ? value : null
);
const moneyAxis = (value) => {
  const absolute = Math.abs(value);
  if (absolute >= 1e6) return `${(value / 1e6).toFixed(1)}M`;
  if (absolute >= 1e3) return `${(value / 1e3).toFixed(0)}K`;
  return `${value}`;
};

function categoryAxis() {
  return {
    type: 'category',
    data: monthLabels,
    boundaryGap: true,
    name: 'Month',
    nameLocation: 'middle',
    nameGap: 34,
    axisLine: { lineStyle: { color: colors.muted } },
    axisTick: { alignWithLabel: true },
    axisLabel: { color: colors.ink, margin: 12 },
  };
}

function valueAxis(name, formatter = undefined) {
  return {
    type: 'value',
    name,
    nameTextStyle: { color: colors.muted, padding: [0, 0, 8, 0] },
    axisLabel: { color: colors.ink, formatter },
    splitLine: { lineStyle: { color: colors.grid, type: 'dashed' } },
  };
}

function baseOption(title, subtitle) {
  return {
    animation: false,
    backgroundColor: colors.background,
    color: [colors.cyan, colors.gold, colors.green, colors.red, colors.blue],
    title: {
      text: title,
      subtext: subtitle,
      left: 30,
      top: 18,
      itemGap: 8,
      textStyle: { color: colors.ink, fontSize: 22, fontWeight: 700 },
      subtextStyle: { color: colors.muted, fontSize: 13 },
    },
    legend: {
      top: 76,
      right: 30,
      textStyle: { color: colors.ink },
    },
    grid: { left: 92, right: 86, top: 142, bottom: 72 },
    xAxis: categoryAxis(),
    yAxis: valueAxis(''),
  };
}

function render(name, option, height = 440) {
  const chart = echarts.init(null, null, {
    renderer: 'svg',
    ssr: true,
    width: 1120,
    height,
  });
  chart.setOption(option);
  fs.writeFileSync(path.join(outputDir, name), chart.renderToSVGString(), 'utf8');
  chart.dispose();
  return name;
}

const generated = [];
if (months.length) {
  const netResults = months.map((item) => toNumber(item.realized_net_profit));
  let runningTotal = 0;
  const cumulative = netResults.map((value) => {
    if (value === null) return null;
    runningTotal += value;
    return runningTotal;
  });
  generated.push(render('monthly-net-profit.svg', {
    ...baseOption(
      'Monthly Net Result',
      'Net of recorded transaction costs | historical simulation',
    ),
    legend: {
      data: singleMonth ? ['Monthly net result'] : ['Monthly net result', 'Cumulative net result'],
      top: 76,
      right: 30,
      textStyle: { color: colors.ink },
    },
    yAxis: singleMonth ? valueAxis('Net result after costs (TWD)', moneyAxis) : [
      valueAxis('Monthly net result (TWD)', moneyAxis),
      {
        ...valueAxis('Cumulative (TWD)', moneyAxis),
        position: 'right',
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: 'Monthly net result',
        type: 'bar',
        barMaxWidth: 58,
        data: netResults,
        itemStyle: {
          color: (params) => (
            Number(params.value) >= 0 ? colors.green : colors.red
          ),
          borderRadius: [4, 4, 0, 0],
        },
        label: {
          show: true,
          position: 'outside',
          color: colors.ink,
          formatter: (params) => moneyAxis(Number(params.value)),
        },
      },
      ...(!singleMonth ? [{
        name: 'Cumulative net result',
        type: 'line',
        yAxisIndex: 1,
        data: cumulative,
        symbolSize: 10,
        lineStyle: { color: colors.cyan, width: 4 },
        itemStyle: { color: colors.cyan },
      }] : []),
    ],
  }));

  generated.push(render('capital-usage.svg', {
    ...baseOption(
      'Monthly Capital Usage',
      'TWD | purchase value is activity, not starting capital; capital is the recorded maximum',
    ),
    legend: {
      data: ['Total purchase value', 'Recorded peak position capital'],
      top: 76,
      right: 30,
      textStyle: { color: colors.ink },
    },
    yAxis: valueAxis('Amount (TWD)', moneyAxis),
    series: [
      {
        name: 'Total purchase value',
        type: 'bar',
        barMaxWidth: 58,
        data: months.map((item) => toNumber(item.buy_notional)),
        itemStyle: { color: colors.blue, borderRadius: [4, 4, 0, 0] },
      },
      {
        name: 'Recorded peak position capital',
        type: 'bar',
        barMaxWidth: 58,
        data: months.map((item) => toNumber(item.max_position_capital)),
        symbolSize: 10,
        lineStyle: { color: colors.gold, width: 4 },
        itemStyle: { color: colors.gold },
      },
    ],
  }));

  generated.push(render('transaction-cost.svg', {
    ...baseOption(
      'Monthly Transaction Costs',
      'Recorded historical-simulation costs | total and largest single order',
    ),
    legend: {
      data: ['Total transaction costs', 'Maximum single-order cost'],
      top: 76,
      right: 30,
      textStyle: { color: colors.ink },
    },
    yAxis: valueAxis('Cost (TWD)', moneyAxis),
    series: [
      {
        name: 'Total transaction costs',
        type: 'bar',
        barMaxWidth: 58,
        data: months.map((item) => toNumber(item.total_transaction_cost)),
        itemStyle: { color: colors.red, borderRadius: [4, 4, 0, 0] },
        label: {
          show: true,
          position: 'outside',
          color: colors.ink,
          formatter: (params) => moneyAxis(Number(params.value)),
        },
      },
      {
        name: 'Maximum single-order cost',
        type: 'bar',
        barMaxWidth: 58,
        data: months.map((item) => toNumber(item.max_order_transaction_cost)),
        symbolSize: 10,
        lineStyle: { color: colors.gold, width: 4 },
        itemStyle: { color: colors.gold },
      },
    ],
  }));
}

process.stdout.write(JSON.stringify(generated));
