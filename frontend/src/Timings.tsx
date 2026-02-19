import { useAtomValue } from "jotai";
import { Fragment, type ReactNode } from "react";

import { Duration } from "./Duration.tsx";
import { Q } from "./Q.tsx";
import { RichCell } from "./RichCell.tsx";
import { Section, SectionTable, SectionTitle } from "./Section.tsx";
import { ReportTableHead, ReportTableRow, ReportTableSection } from "./Table.tsx";
import {
  type IncrementalBuildStepName,
  IncrementalBuildSteps,
  type Report,
  type ReportTitle,
  type StepName,
  type StepReport,
  Steps,
  type Test,
  type TestName,
  pivotReportAtom,
  selectedReportsAtom,
  selectionAtom,
  urlOf,
  vm,
} from "./atoms.ts";
import { DefaultMap } from "./defaultmap.ts";
import { durationFromTotal, durationTotal, serializeDuration } from "./time.ts";
import { durationTrend } from "./trends.ts";
import {
  bigintSqrt,
  determineUniformRevForTest,
  determineUniformTestRunnerForTest,
  mean,
  variance,
} from "./utils.ts";

type MostVariableSteps = {
  testName: TestName;
  values: Record<ReportTitle, string>;
  stddev: string;
}[];

export function TimingSections() {
  return (
    <>
      {Object.keys(Steps).map((stepName) => (
        <TimingSection key={stepName} stepName={stepName as StepName} />
      ))}
      <IncrementalBuildTimingSection />
    </>
  );
}

function TimingSection({ stepName }: { stepName: StepName }) {
  const selection = useAtomValue(selectionAtom);
  const selectedReports = useAtomValue(selectedReportsAtom);
  const pivotReport = useAtomValue(pivotReportAtom);
  const mostVariableSteps = findMostVariableSteps(selectedReports, pivotReport, stepName);
  const isSingleReport = selectedReports.length === 1;

  let title;
  if (isSingleReport) {
    title = (
      <>
        {`Top ${mostVariableSteps.length} slowest projects `}
        <Q>
          Ma'at shows the top 10 projects with the slowest timing performance. Projects are sorted
          by execution time (slowest first), then alphabetically. Only projects with successful
          timing measurements are included.
        </Q>
      </>
    );
  } else {
    title = (
      <>
        {`Top ${mostVariableSteps.length} most variable projects `}
        <Q>
          Ma'at shows the top 10 projects with the most variable timing performance compared to a
          reference report. Projects are sorted by variance (highest first), then alphabetically.
          Only projects with at least 2 valid timing measurements are included. Variance is
          calculated using the reference report's timing as the expected value, measuring how much
          other timings deviate from this baseline.
        </Q>
      </>
    );
  }

  return (
    <Section id={`timings-${stepName}`}>
      <SectionTitle>{Steps[stepName].humanName} Timings</SectionTitle>
      <SectionTable>
        <ReportTableHead />
        <ReportTableSection title="Summary" />
        <tbody>
          <ReportTableRow
            title="Successful Runs Mean"
            cell={(report) => {
              const value = report.metrics[Steps[stepName].meanKey];
              const pivotValue = pivotReport?.metrics[Steps[stepName].meanKey] ?? null;
              const allValues = selectedReports.map((r) => r.metrics[Steps[stepName].meanKey]);
              const trend = !isSingleReport && durationTrend(value, pivotValue, allValues);
              return <RichCell value={value && <Duration value={value} />} trend={trend} />;
            }}
          />
          <ReportTableRow
            title="Successful Runs Median"
            cell={(report) => {
              const value = report.metrics[Steps[stepName].medianKey];
              const pivotValue = pivotReport?.metrics[Steps[stepName].medianKey] ?? null;
              const allValues = selectedReports.map((r) => r.metrics[Steps[stepName].medianKey]);
              const trend = !isSingleReport && durationTrend(value, pivotValue, allValues);
              return <RichCell value={value && <Duration value={value} />} trend={trend} />;
            }}
          />
        </tbody>
        {mostVariableSteps.length > 0 && (
          <>
            <ReportTableSection title={title} />
            <tbody>
              {mostVariableSteps.map(({ testName, values, stddev }) => {
                let titleSecondRowParts: ReactNode[] = [];

                const uniformRev = determineUniformRevForTest(vm, selection, testName);
                if (uniformRev) {
                  titleSecondRowParts.push(uniformRev);
                }

                const uniformTestRunner = determineUniformTestRunnerForTest(vm, selection, testName);
                titleSecondRowParts.push(
                  <Fragment key="test-runner">
                    <span className="badge badge-sm badge-outline">{uniformTestRunner}</span>
                  </Fragment>,
                );

                if (!isSingleReport) {
                  titleSecondRowParts.push(
                    <Fragment key="stddev">
                      σ=
                      <Duration value={stddev} />
                    </Fragment>,
                  );
                }

                titleSecondRowParts = intersperse(titleSecondRowParts, ", ");

                return (
                  <ReportTableRow
                    key={testName}
                    title={
                      <>
                        {testName}
                        <br />
                        <span className="text-base-content/60 text-xs font-normal">
                          {titleSecondRowParts}
                        </span>
                      </>
                    }
                    cell={(report) => {
                      const value = values[report.title] ?? null;
                      const pivotValue = (pivotReport && values[pivotReport.title]) ?? null;
                      const allValues = selectedReports.map((r) => values[r.title] ?? null);
                      const trend = !isSingleReport && durationTrend(value, pivotValue, allValues);

                      const test = report.tests.find((t) => t.name === testName);
                      const logsHref = test && urlOf(test.logsHref);
                      const rev = uniformRev ? undefined : test?.rev;

                      return (
                        <RichCell
                          value={value && <Duration value={value} />}
                          trend={trend}
                          href={logsHref}
                          rev={rev}
                        />
                      );
                    }}
                  />
                );
              })}
            </tbody>
          </>
        )}
      </SectionTable>
    </Section>
  );
}

type IncrementalBuildRow = {
  testName: TestName;
  coldBuild: Record<ReportTitle, string>;
  values: Record<ReportTitle, string>;
  speedup: Record<ReportTitle, number>;
  meanSpeedup: number;
};

function IncrementalBuildTimingSection() {
  const selectedReports = useAtomValue(selectedReportsAtom);
  const pivotReport = useAtomValue(pivotReportAtom);
  const isSingleReport = selectedReports.length === 1;

  return (
    <Section id="timings-incremental-build">
      <SectionTitle>Incremental Build Timings</SectionTitle>
      <SectionTable>
        <ReportTableHead />
        <ReportTableSection title="Summary" />
        <tbody>
          {(Object.keys(IncrementalBuildSteps) as IncrementalBuildStepName[]).map((stepName) => {
            const meta = IncrementalBuildSteps[stepName];
            return (
              <Fragment key={stepName}>
                <ReportTableRow
                  title={`${meta.humanName} Mean`}
                  cell={(report) => {
                    const value = report.metrics[meta.meanKey];
                    const pivotValue = pivotReport?.metrics[meta.meanKey] ?? null;
                    const allValues = selectedReports.map((r) => r.metrics[meta.meanKey]);
                    const trend = !isSingleReport && durationTrend(value, pivotValue, allValues);
                    return <RichCell value={value && <Duration value={value} />} trend={trend} />;
                  }}
                />
                <ReportTableRow
                  title={`${meta.humanName} Median`}
                  cell={(report) => {
                    const value = report.metrics[meta.medianKey];
                    const pivotValue = pivotReport?.metrics[meta.medianKey] ?? null;
                    const allValues = selectedReports.map((r) => r.metrics[meta.medianKey]);
                    const trend = !isSingleReport && durationTrend(value, pivotValue, allValues);
                    return <RichCell value={value && <Duration value={value} />} trend={trend} />;
                  }}
                />
              </Fragment>
            );
          })}
        </tbody>
        {(Object.keys(IncrementalBuildSteps) as IncrementalBuildStepName[]).map((stepName) => {
          const meta = IncrementalBuildSteps[stepName];
          const rows = findIncrementalBuildRows(selectedReports, meta.timeKey);
          if (rows.length === 0) return null;
          return (
            <Fragment key={stepName}>
              <ReportTableSection
                title={
                  <>
                    {`Top ${rows.length} projects – ${meta.humanName} speedup `}
                    <Q>
                      Shows projects sorted by speedup ratio (cold build time / incremental build
                      time). Higher values indicate bigger gains from incremental compilation. Cold
                      and incremental timings are measured from the same incremental-step command.
                      For older reports, cold timing falls back to the regular build step time.
                    </Q>
                  </>
                }
              />
              <tbody>
                {rows.map(({ testName, coldBuild, values, speedup }) => (
                  <ReportTableRow
                    key={testName}
                    title={
                      <>
                        {testName}
                        <br />
                        <span className="text-base-content/60 text-xs font-normal">
                          speedup:{" "}
                          {selectedReports
                            .map((r) => {
                              const value = speedup[r.title];
                              return value != null ? `${value.toFixed(1)}×` : "—";
                            })
                            .join(", ")}
                        </span>
                      </>
                    }
                    cell={(report) => {
                      const coldVal = coldBuild[report.title] ?? null;
                      const incrVal = values[report.title] ?? null;
                      if (!coldVal || !incrVal) return "—";
                      return (
                        <>
                          <Duration value={coldVal} /> → <Duration value={incrVal} />
                        </>
                      );
                    }}
                  />
                ))}
              </tbody>
            </Fragment>
          );
        })}
      </SectionTable>
    </Section>
  );
}

function findIncrementalBuildRows(
  selectedReports: Report[],
  timeKey: "incrementalBuildTime" | "incrementalBuildNoTestTime",
): IncrementalBuildRow[] {
  const testNames = new Set<TestName>();
  for (const report of selectedReports) {
    for (const test of report.tests) {
      if (test[timeKey]) {
        testNames.add(test.name);
      }
    }
  }

  const rows: IncrementalBuildRow[] = [];
  for (const testName of testNames) {
    const coldBuild: Record<ReportTitle, string> = {} as Record<ReportTitle, string>;
    const values: Record<ReportTitle, string> = {} as Record<ReportTitle, string>;
    const speedup: Record<ReportTitle, number> = {} as Record<ReportTitle, number>;
    const speedups: number[] = [];

    for (const report of selectedReports) {
      const test = report.tests.find((t) => t.name === testName);
      const incrTime = test?.[timeKey];
      const coldTime =
        timeKey === "incrementalBuildNoTestTime"
          ? (test?.coldBuildNoTestTime ?? test?.build?.executionTime)
          : (test?.coldBuildTime ?? test?.build?.executionTime);
      if (incrTime) {
        values[report.title] = incrTime;
        if (coldTime) {
          coldBuild[report.title] = coldTime;
          const coldTotal = durationTotal(coldTime);
          const incrTotal = durationTotal(incrTime);
          if (incrTotal > 0n) {
            const s = Number(coldTotal) / Number(incrTotal);
            speedup[report.title] = s;
            speedups.push(s);
          }
        }
      }
    }

    if (speedups.length > 0) {
      const meanSpeedup = speedups.reduce((a, b) => a + b, 0) / speedups.length;
      rows.push({ testName, coldBuild, values, speedup, meanSpeedup });
    }
  }

  return rows.sort((a, b) => a.meanSpeedup - b.meanSpeedup).slice(0, 10);
}

function findMostVariableSteps(
  selectedReports: Report[],
  pivotReport: Report | undefined,
  stepName: StepName,
): MostVariableSteps {
  if (!pivotReport || selectedReports.length === 0) {
    return [];
  }

  function isSuccessfulStep(stepReport: StepReport | null): stepReport is StepReport & {
    executionTime: string;
    exitCode: 0;
  } {
    return stepReport != null && stepReport.executionTime != null && stepReport.exitCode === 0;
  }

  // Single-report mode: show top N slowest timings.
  if (selectedReports.length === 1) {
    const report = selectedReports[0]!;
    return report.tests
      .filter((test) => isSuccessfulStep(test[stepName]))
      .map((test) => ({
        testName: test.name,
        values: { [report.title]: test[stepName]!.executionTime! },
        executionTime: durationTotal(test[stepName]!.executionTime!),
      }))
      .sort(
        (a, b) => Number(b.executionTime - a.executionTime) || a.testName.localeCompare(b.testName),
      )
      .slice(0, 10)
      .map(({ executionTime, ...props }) => ({
        ...props,
        stddev: serializeDuration(durationFromTotal(executionTime)),
      }));
  }

  // Multi-report mode: show most variable timings (existing logic).

  // List of tests from the pivot report which passed the step successfully.
  const pivotSuccessfulTests = new Set(
    pivotReport.tests.filter((t) => isSuccessfulStep(t[stepName])).map((t: Test) => t.name),
  );

  // Test -> Selected report -> Execution time
  const candidatesMap: DefaultMap<TestName, Map<ReportTitle, string>> = new DefaultMap(
    () => new Map(),
  );
  for (const report of selectedReports) {
    for (const test of report.tests) {
      if (pivotSuccessfulTests.has(test.name)) {
        const step = test[stepName];
        if (isSuccessfulStep(step)) {
          candidatesMap.get(test.name).set(report.title, step.executionTime);
        }
      }
    }
  }

  // Remove tests that have less than 2 successful step runs among selected reports (of which 1 will be from the pivot
  // report because of filtering while collecting pivotSuccessfulTests).
  for (const [testName, timings] of candidatesMap.entries()) {
    const successfulCount = Array.from(timings.values()).filter((v) => v != null).length;
    if (successfulCount < 2) {
      candidatesMap.delete(testName);
    }
  }

  // Transform candidatesMap into the desired form.
  const candidates = Array.from(candidatesMap.entries()).map(
    ([testName, timings]) => ({ testName, values: Object.fromEntries(timings) }) as const,
  );

  // Sort by variance (highest first) and limit to at most 10.
  return candidates
    .map(({ testName, values }) => {
      const samples = Object.values(values).map((v) => durationTotal(v));
      const pivotSample = values[pivotReport.title];
      const xbar = pivotSample ? durationTotal(pivotSample) : mean(samples);
      return {
        testName,
        values,
        variance: variance(samples, xbar),
      } as const;
    })
    .sort((a, b) => Number(b.variance - a.variance) || a.testName.localeCompare(b.testName))
    .map(
      ({ variance, ...props }) =>
        ({
          ...props,
          stddev: serializeDuration(durationFromTotal(bigintSqrt(variance))),
        }) as const,
    )
    .slice(0, 10);
}

function intersperse<T, S>(items: readonly T[], sep: S): (T | S)[] {
  const out: (T | S)[] = [];
  let first = true;
  for (const item of items) {
    if (!first) out.push(sep);
    out.push(item);
    first = false;
  }
  return out;
}
