import * as tinyduration from "tinyduration";

const durationFormat = new Intl.DurationFormat(undefined, {
  style: "narrow",
});

export interface TimeComponentProps {
  value: string;
}

export function DateTime({ value }: TimeComponentProps) {
  return new Date(value).toLocaleString();
}

export function Duration({ value }: TimeComponentProps) {
  const duration = parseDurationAsTemporal(value);
  return durationFormat.format(duration);
}

// WORKAROUND: Currently, TypeScript doesn't provide `DurationFormat` types.
//   https://github.com/microsoft/TypeScript/pull/60646
declare namespace Intl {
  type DurationTimeFormatUnit =
    | "years"
    | "months"
    | "weeks"
    | "days"
    | "hours"
    | "minutes"
    | "seconds"
    | "milliseconds"
    | "microseconds"
    | "nanoseconds";

  type DurationType = Partial<Record<DurationTimeFormatUnit, number>>;

  class DurationFormat {
    constructor(locales?: globalThis.Intl.LocalesArgument, options?: unknown);

    format(duration: DurationType): string;
  }
}

function parseDurationAsTemporal(value: string): Intl.DurationType {
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
