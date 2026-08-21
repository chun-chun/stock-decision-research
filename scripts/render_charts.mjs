#!/usr/bin/env node

import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import * as echarts from 'echarts';

const outputDirectory = process.argv[2];
if (!outputDirectory) {
  throw new Error('An output directory is required.');
}

const records = JSON.parse(readFileSync(0, 'utf8'));
if (!Array.isArray(records)) {
  throw new Error('Chart input must be an array of monthly records.');
}

mkdirSync(outputDirectory, { recursive: true });

const palette = ['#22C55E', '#38BDF8', '#A78BFA', '#FBBF24', '#FB7185', '#2DD4BF'];
const colors = {
  background: '#111827',
  text: '#F9FAFB',
  muted: '#9CA3AF',
  grid: '#374151',
};

function isNumber(value) {
  return typeof value === 'number' && Number.isFinite(value);
}

function baseOption(title, months, { boundaryGap = false, yAxis = {} } = {}) {
  return {
    animation: false,
    backgroundColor: colors.background,
    color: palette,
    textStyle: {
      color: colors.text,
      fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    },
    title: {
      text: title,
      left: 28,
      top: 22,
      textStyle: { color: colors.text, fontSize: 24, fontWeight: 600 },
    },
    legend: {
      top: 62,
      left: 28,
      itemWidth: 24,
      itemHeight: 10,
      textStyle: { color: colors.muted, fontSize: 13 },
    },
    grid: { left: 76, right: 38, top: 112, bottom: 72 },
    xAxis: {
      type: 'category',
      data: months,
      boundaryGap,
      axisLine: { lineStyle: { color: colors.grid } },
      axisTick: { show: false },
      axisLabel: { color: colors.muted, rotate: months.length > 12 ? 45 : 0, margin: 16 },
    },
    yAxis: {
      type: 'value',
      scale: true,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: colors.muted },
      splitLine: { lineStyle: { color: colors.grid, opacity: 0.7 } },
      ...yAxis,
    },
    series: [],
  };
}

function render(name, option, width = 1400, height = 720) {
  const chart = echarts.init(null, null, { renderer: 'svg', ssr: true, width, height });
  chart.setOption(option);
  writeFileSync(join(outputDirectory, name), chart.renderToSVGString(), 'utf8');
  chart.dispose();
}

function buildRewardTrend(months) {
  const groups = new Map();
  records.forEach((record, index) => {
    const group = record.reward_definition.comparable_group;
    if (!groups.has(group)) groups.set(group, []);
    groups.get(group).push([index, record]);
  });

  const option = baseOption('Monthly Reward Trend', months, {
    yAxis: { name: 'Reward', nameTextStyle: { color: colors.muted, padding: [0, 0, 8, 0] } },
  });
  option.legend.data = [];

  [...groups.entries()].forEach(([group, entries], groupIndex) => {
    const color = palette[groupIndex % palette.length];
    const mean = Array(months.length).fill(null);
    const median = Array(months.length).fill(null);
    const p25 = Array(months.length).fill(null);
    const p75 = Array(months.length).fill(null);

    entries.forEach(([index, record]) => {
      const reward = record.reward;
      mean[index] = reward.mean;
      median[index] = reward.median;
      if (isNumber(reward.p25) && isNumber(reward.p75)) {
        p25[index] = reward.p25;
        p75[index] = reward.p75;
      }
    });

    const meanName = `${group} mean`;
    const medianName = `${group} median`;
    option.legend.data.push(meanName, medianName);
    option.series.push(
      {
        name: `${group} p25`,
        type: 'line',
        data: p25,
        symbol: 'none',
        lineStyle: { color, width: 1, type: 'dotted', opacity: 0.35 },
        silent: true,
      },
      {
        name: `${group} p75`,
        type: 'line',
        data: p75,
        symbol: 'none',
        lineStyle: { color, width: 1, type: 'dotted', opacity: 0.35 },
        silent: true,
      },
      {
        name: meanName,
        type: 'line',
        data: mean,
        connectNulls: false,
        symbol: 'circle',
        symbolSize: 9,
        showSymbol: true,
        lineStyle: { color, width: 3 },
        itemStyle: { color, borderColor: colors.background, borderWidth: 2 },
      },
      {
        name: medianName,
        type: 'line',
        data: median,
        connectNulls: false,
        symbol: 'diamond',
        symbolSize: 8,
        lineStyle: { color, width: 2, type: 'dashed', opacity: 0.75 },
        itemStyle: { color },
      },
    );
  });

  option.series.push({
    name: 'Zero reference',
    type: 'line',
    data: Array(months.length).fill(0),
    symbol: 'none',
    lineStyle: { color: colors.muted, width: 1, type: 'dotted', opacity: 0.65 },
    silent: true,
  });
  return option;
}

function buildSampleCount(months) {
  const option = baseOption('Monthly Reward Sample Count', months, {
    boundaryGap: true,
    yAxis: { name: 'Samples', min: 0, nameTextStyle: { color: colors.muted } },
  });
  option.legend.show = false;
  option.series = [{
    name: 'Samples',
    type: 'bar',
    data: records.map((record) => record.reward.sample_count),
    barMaxWidth: 52,
    itemStyle: {
      color: palette[1],
      borderRadius: [6, 6, 0, 0],
    },
    label: {
      show: records.length <= 18,
      position: 'top',
      color: colors.muted,
    },
  }];
  return option;
}

function buildPositiveRate(months) {
  const option = baseOption('Monthly Positive Reward Rate', months, {
    yAxis: {
      name: 'Positive Reward (%)',
      min: 0,
      max: 100,
      nameTextStyle: { color: colors.muted },
      axisLabel: { color: colors.muted, formatter: '{value}%' },
    },
  });
  option.legend.show = false;
  option.series = [{
    name: 'Positive Reward',
    type: 'line',
    data: records.map((record) => isNumber(record.reward.positive_rate)
      ? record.reward.positive_rate * 100
      : null),
    symbol: 'circle',
    symbolSize: 10,
    lineStyle: { color: palette[0], width: 3 },
    itemStyle: { color: palette[0], borderColor: colors.background, borderWidth: 2 },
    areaStyle: { color: palette[0], opacity: 0.1 },
  }];
  return option;
}

const generated = [];
const months = records.map((record) => record.report_month);

if (records.some((record) => isNumber(record.reward.mean))) {
  render('reward-trend.svg', buildRewardTrend(months));
  generated.push('reward-trend.svg');
}

if (records.length > 0) {
  render('reward-sample-count.svg', buildSampleCount(months), 1400, 620);
  generated.push('reward-sample-count.svg');
}

if (records.some((record) => isNumber(record.reward.positive_rate))) {
  render('reward-positive-rate.svg', buildPositiveRate(months), 1400, 620);
  generated.push('reward-positive-rate.svg');
}

process.stdout.write(JSON.stringify(generated));
