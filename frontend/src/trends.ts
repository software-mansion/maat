import { durationFromTotal, durationTotal, serializeDuration } from "./time.ts";

export interface Trend {
  ratio: number;
  isExtreme: boolean;
  symbol: string;
  percentage: string;
  absoluteDiff: string | null;
  colorClass: string;
}

export function durationTrend(
  value: string | null,
  referenceValue: string | null,
  allValues: (string | null)[],
): Trend | null {
  if (!value) {
    return null;
  }

  const durationTotalMs = (timeStr: string): bigint => durationTotal(timeStr, "milliseconds");
  const durationTotalSeconds = (timeStr: string): number => Number(durationTotalMs(timeStr)) / 1000;

  const valueMs = durationTotalMs(value);
  const valueSeconds = durationTotalSeconds(value);

  let ratio: number;
  let diffMs: bigint | null = null;
  if (!referenceValue) {
    ratio = -Infinity;
  } else {
    const refMs = durationTotalMs(referenceValue);
    const refSeconds = durationTotalSeconds(referenceValue);
    diffMs = valueMs - refMs;
    if (refSeconds === 0) {
      if (valueSeconds === 0) {
        ratio = 0;
      } else if (valueSeconds > 0) {
        ratio = Infinity;
      } else {
        ratio = -Infinity;
      }
    } else {
      ratio = (valueSeconds - refSeconds) / refSeconds;
    }
  }

  // Find extremes for isExtreme calculation.
  const nonNullValues = allValues.filter((v) => v !== null).map((v) => durationTotalMs(v!));
  const minValue = nonNullValues.length > 0 ? nonNullValues.reduce((a, b) => (a < b ? a : b)) : null;
  const maxValue = nonNullValues.length > 0 ? nonNullValues.reduce((a, b) => (a > b ? a : b)) : null;
  const isExtreme =
    (minValue !== null && valueMs === minValue) ||
    (maxValue !== null && valueMs === maxValue);

  // Generate symbol.
  let symbol: string;
  if (ratio < 0) {
    symbol = isExtreme ? "⤓" : "↓";
  } else if (ratio > 0) {
    symbol = isExtreme ? "⤒" : "↑";
  } else {
    symbol = "=";
  }

  // Generate percentage.
  let percentage: string;
  if (ratio === Infinity) {
    percentage = "∞";
  } else if (ratio === -Infinity) {
    percentage = "-∞";
  } else {
    percentage = `${Math.round(ratio * 100)}%`;
  }

  // Generate absolute diff.
  let absoluteDiff: string | null = null;
  if (diffMs !== null) {
    const absDiffMs = diffMs < 0n ? -diffMs : diffMs;
    const sign = diffMs < 0n ? "-" : "+";
    absoluteDiff = `${sign}${serializeDuration(durationFromTotal(absDiffMs, "milliseconds"))}`;
  }

  // Generate colour class.
  let colorClass: string;
  if (ratio < 0) {
    colorClass = "text-success";
  } else if (ratio > 0) {
    colorClass = "text-error";
  } else {
    colorClass = "text-base-content/60";
  }

  return {
    ratio,
    isExtreme,
    symbol,
    percentage,
    absoluteDiff,
    colorClass,
  };
}
