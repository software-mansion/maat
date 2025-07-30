import type { ReportTitle, Test, TestName, ViewModel } from "./atoms.ts";

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
