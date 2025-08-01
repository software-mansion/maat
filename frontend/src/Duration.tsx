import { durationRoundToSeconds, parseDuration } from "./time.ts";

const durationFormat = new Intl.DurationFormat(undefined, {
  style: "narrow",
});

export function Duration({ value }: { value: string }) {
  const duration = durationRoundToSeconds(parseDuration(value));
  return durationFormat.format(duration);
}
