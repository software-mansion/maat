import { useAtomValue } from "jotai";
import { applySelection, pivotAtom, selectionAtom, viewModelAtom } from "./atoms.ts";
import { Section, SectionTable, SectionTitle } from "./Section.tsx";
import { ReportTableHead, ReportTableRow, ReportTableSection } from "./Table.tsx";
import { durationTrend, MetricWithTrend } from "./trends.tsx";

const Steps = {
  Build: {
    meanKey: "meanBuildTime",
    medianKey: "medianBuildTime",
  },
  Lint: {
    meanKey: "meanLintTime",
    medianKey: "medianLintTime",
  },
  Test: {
    meanKey: "meanTestTime",
    medianKey: "medianTestTime",
  },
  LS: {
    meanKey: "meanLsTime",
    medianKey: "medianLsTime",
  },
} as const;

export function TimingSections() {
  return (
    <>
      {Object.keys(Steps).map((stepName) => (
        <TimingSection key={stepName} stepName={stepName as keyof typeof Steps} />
      ))}
    </>
  );
}

function TimingSection({ stepName }: { stepName: keyof typeof Steps }) {
  const vm = useAtomValue(viewModelAtom);
  const selection = useAtomValue(selectionAtom);
  const pivot = useAtomValue(pivotAtom);

  const selectedReports = applySelection(vm.reports, selection);
  const pivotReport = vm.reports[pivot];

  return (
    <Section>
      <SectionTitle>{stepName} Timings</SectionTitle>
      <SectionTable>
        <ReportTableHead />
        <ReportTableSection title="Summary" />
        <tbody>
          <ReportTableRow
            title="Successful Runs Mean"
            cell={(report) => {
              const value = report.metrics[Steps[stepName].meanKey];
              const pivotValue = pivotReport.metrics[Steps[stepName].meanKey];
              const allValues = selectedReports.map((r) => r.metrics[Steps[stepName].meanKey]);
              const trend = durationTrend(value, pivotValue, allValues);
              return <MetricWithTrend value={value} trend={trend} />;
            }}
          />
          <ReportTableRow
            title="Successful Runs Median"
            cell={(report) => {
              const value = report.metrics[Steps[stepName].medianKey];
              const pivotValue = pivotReport.metrics[Steps[stepName].medianKey];
              const allValues = selectedReports.map((r) => r.metrics[Steps[stepName].medianKey]);
              const trend = durationTrend(value, pivotValue, allValues);
              return <MetricWithTrend value={value} trend={trend} />;
            }}
          />
        </tbody>
      </SectionTable>
    </Section>
  );
}
