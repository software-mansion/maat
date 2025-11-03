import type { ReportTitle, Test, TestName, TestRunner, ViewModel } from "./atoms.ts";

/** Calculate uniformRev if all selected runs of a test share the same revision. */
export function determineUniformRevForTest(
  vm: ViewModel,
  selection: ReportTitle[],
  testName: TestName,
) {
  let candidate: string | undefined = undefined;
  for (const reportTitle of selection) {
    const report = vm.reports[reportTitle];
    const test = report?.tests?.find((t: Test) => t.name === testName);
    if (test) {
      if (candidate === undefined) {
        candidate = test.rev;
      } else if (candidate !== test.rev) {
        return undefined;
      }
    }
  }

  return candidate;
}

/** Calculate uniform test runner if all selected runs of a test share the same test runner. */
export function determineUniformTestRunnerForTest(
  vm: ViewModel,
  selection: ReportTitle[],
  testName: TestName,
): TestRunner | undefined {
  let candidate: TestRunner | undefined | null = undefined;
  for (const reportTitle of selection) {
    const report = vm.reports[reportTitle];
    const test = report?.tests?.find((t: Test) => t.name === testName);
    if (test) {
      if (candidate === undefined) {
        candidate = test.testRunner;
      } else if (candidate !== test.testRunner) {
        return undefined;
      }
    }
  }

  return candidate ?? undefined;
}

export function variance(samples: bigint[], xbar: bigint): bigint {
  const n = BigInt(samples.length - 1);
  if (!n) return 0n;

  const sumSquaredDiffs = samples.reduce((sum, sample) => {
    const diff = sample - xbar;
    return sum + diff * diff;
  }, 0n);

  return sumSquaredDiffs / n;
}

/**
 * Compute the square root of the BigInt n, truncated towards 0 to an integer.
 *
 * Source: https://github.com/waldemarhorwat/integer-roots/blob/cd26c522219346d874391170c11731bf759f6b35/roots.js
 */
export function bigintSqrt(n: bigint): bigint {
  if (n < 0n) throw RangeError("Square root of negative BigInt");
  if (n === 0n) return 0n;
  const w = BigInt(n.toString(2).length - 1); // log2(n)
  let x = 1n << (w >> 1n); // x is the initial guess x0 here
  let next = (x + n / x) >> 1n;
  do {
    x = next;
  } while ((next = (x + n / x) >> 1n) < x);
  return x;
}

export function mean(samples: bigint[]): bigint {
  return samples.reduce((sum, sample) => sum + sample, 0n) / BigInt(samples.length);
}
