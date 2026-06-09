import { durationRoundToSeconds, durationTotal, parseDuration } from "./time.ts";

const durationFormat = new Intl.DurationFormat(undefined, {
  style: "narrow",
});

export function Duration({ value }: { value: string }) {
  const duration = durationRoundToSeconds(parseDuration(value));
  // A zero duration (e.g. "PT0S", produced by a zero diff or zero stddev) parses
  // to an empty record, and `Intl.DurationFormat.format` throws "Invalid duration"
  // on a duration without any fields. Render it explicitly instead.
  if (durationTotal(duration) === 0n) {
    return "0s";
  }
  return durationFormat.format(duration);
}
