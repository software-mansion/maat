/// <reference types="vite/client" />

declare module "virtual:maat-view-model" {
  const vm: unknown;
  export default vm;
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
