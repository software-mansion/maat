import * as tinyduration from "tinyduration";

export function parseDuration(value: string): Intl.DurationType {
  const duration = tinyduration.parse(value);
  const normalized: Intl.DurationType = {};

  // Copy all non-seconds values as-is (they're assumed to be already integers).
  for (const [key, val] of Object.entries(duration)) {
    if (key !== "seconds" && val !== undefined) {
      normalized[key as keyof Intl.DurationType] = val;
    }
  }

  // Handle fractional seconds.
  if (duration.seconds !== undefined && duration.seconds !== 0) {
    const integerSeconds = Math.floor(Math.abs(duration.seconds));
    const fractionalPart = Math.abs(duration.seconds) - integerSeconds;

    // Set integer seconds (preserving sign).
    normalized.seconds = duration.seconds >= 0 ? integerSeconds : -integerSeconds;

    // Convert fractional seconds to milliseconds.
    if (fractionalPart > 0) {
      const additionalMilliseconds = fractionalPart * 1000;
      const existingMilliseconds = normalized.milliseconds || 0;
      normalized.milliseconds = Math.floor(
        existingMilliseconds +
          (duration.seconds >= 0 ? additionalMilliseconds : -additionalMilliseconds),
      );
    }
  }

  return normalized;
}

export function serializeDuration(duration: Intl.DurationType): string {
  return tinyduration.serialize({
    years: duration.years,
    months: duration.months,
    weeks: duration.weeks,
    days: duration.days,
    hours: duration.hours,
    minutes: duration.minutes,
    seconds:
      (duration.seconds ?? 0) +
      (duration.milliseconds ?? 0) / 1_000 +
      (duration.microseconds ?? 0) / 1_000_000 +
      (duration.nanoseconds ?? 0) / 1_000_000_000,
  });
}

// IMPORTANT: Property order is significant.
const toNanoseconds = {
  years: 365n * 24n * 60n * 60n * 1000n * 1000n * 1000n,
  months: 30n * 24n * 60n * 60n * 1000n * 1000n * 1000n,
  weeks: 7n * 24n * 60n * 60n * 1000n * 1000n * 1000n,
  days: 24n * 60n * 60n * 1000n * 1000n * 1000n,
  hours: 60n * 60n * 1000n * 1000n * 1000n,
  minutes: 60n * 1000n * 1000n * 1000n,
  seconds: 1000n * 1000n * 1000n,
  milliseconds: 1000n * 1000n,
  microseconds: 1000n,
  nanoseconds: 1n,
} as const;

export function durationTotal(
  duration: Intl.DurationType | string,
  unit: Intl.DurationTimeFormatUnit = "nanoseconds",
): bigint {
  if (typeof duration === "string") {
    duration = parseDuration(duration);
  }

  const total =
    BigInt(duration.years ?? 0) * toNanoseconds.years +
    BigInt(duration.months ?? 0) * toNanoseconds.months +
    BigInt(duration.weeks ?? 0) * toNanoseconds.weeks +
    BigInt(duration.days ?? 0) * toNanoseconds.days +
    BigInt(duration.hours ?? 0) * toNanoseconds.hours +
    BigInt(duration.minutes ?? 0) * toNanoseconds.minutes +
    BigInt(duration.seconds ?? 0) * toNanoseconds.seconds +
    BigInt(duration.milliseconds ?? 0) * toNanoseconds.milliseconds +
    BigInt(duration.microseconds ?? 0) * toNanoseconds.microseconds +
    BigInt(duration.nanoseconds ?? 0) * toNanoseconds.nanoseconds;

  return total / toNanoseconds[unit];
}

export function durationFromTotal(
  total: bigint,
  unit: Intl.DurationTimeFormatUnit = "nanoseconds",
): Intl.DurationType {
  const totalNs = total * toNanoseconds[unit];

  const result: Intl.DurationType = {};
  let remaining = totalNs;
  // NOTE: This depends on the order of properties in toNanoseconds object.
  for (const [unitName, unitNs] of Object.entries(toNanoseconds)) {
    if (remaining === 0n) break;

    const value = remaining / unitNs;
    remaining = remaining % unitNs;
    if (value !== 0n) {
      result[unitName as keyof Intl.DurationType] = Number(value);
    }
  }

  return result;
}

export function durationRoundToSeconds(duration: Intl.DurationType): Intl.DurationType {
  const result: Intl.DurationType = {
    years: duration.years,
    months: duration.months,
    weeks: duration.weeks,
    days: duration.days,
    hours: duration.hours,
    minutes: duration.minutes,
    seconds: duration.seconds ?? 0,
  };

  // If this duration is sub-0-seconds, then do not do any rounding.
  if (Object.values(result).every((v) => v === undefined || v === 0)) {
    return duration;
  }

  // Convert smaller units to fractional seconds
  const additionalSeconds =
    (duration.milliseconds ?? 0) / 1000 +
    (duration.microseconds ?? 0) / 1_000_000 +
    (duration.nanoseconds ?? 0) / 1_000_000_000;

  if (additionalSeconds > 0) {
    result.seconds = (result.seconds ?? 0) + Math.round(additionalSeconds);
  }

  // Normalize to handle carry-over (e.g., 60 seconds -> 1 minute).
  return durationFromTotal(durationTotal(result, "seconds"), "seconds");
}
