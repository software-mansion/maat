import { durationTotal } from "./time.tsx";

export interface Trend {
  ratio: number;
  isExtreme: boolean;
  symbol: string;
  percentage: string;
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

  const durationTotalSeconds = (timeStr: string): number =>
    Number(durationTotal(timeStr, "milliseconds")) / 1000;

  const valueSeconds = durationTotalSeconds(value);

  let ratio: number;
  if (!referenceValue) {
    // If reference is null (failure), any value is an infinite improvement.
    ratio = -Infinity;
  } else {
    const refSeconds = durationTotalSeconds(referenceValue);
    if (refSeconds === 0) {
      if (valueSeconds === 0) {
        ratio = 0; // No change: 0 → 0.
      } else if (valueSeconds > 0) {
        ratio = Infinity; // Infinite increase: 0 → positive.
      } else {
        ratio = -Infinity; // Infinite decrease: 0 → negative.
      }
    } else {
      ratio = (valueSeconds - refSeconds) / refSeconds;
    }
  }

  // Find extremes for isExtreme calculation.
  const nonNullValues = allValues.filter((v) => v !== null).map((v) => durationTotalSeconds(v!));
  const minValue = nonNullValues.length > 0 ? Math.min(...nonNullValues) : null;
  const maxValue = nonNullValues.length > 0 ? Math.max(...nonNullValues) : null;
  const isExtreme =
    (minValue !== null && valueSeconds === minValue) ||
    (maxValue !== null && valueSeconds === maxValue);

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
    colorClass,
  };
}
