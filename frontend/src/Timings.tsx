import { useAtomValue } from "jotai";
import { pivotAtom, selectedReportsAtom, type StepName, Steps, viewModelAtom } from "./atoms.ts";
import { Section, SectionTable, SectionTitle } from "./Section.tsx";
import { ReportTableHead, ReportTableRow, ReportTableSection } from "./Table.tsx";
import { durationTrend, MetricWithTrend } from "./trends.tsx";

export function TimingSections() {
  return (
    <>
      {Object.keys(Steps).map((stepName) => (
        <TimingSection key={stepName} stepName={stepName as StepName} />
      ))}
    </>
  );
}

function TimingSection({ stepName }: { stepName: StepName }) {
  const vm = useAtomValue(viewModelAtom);
  const selectedReports = useAtomValue(selectedReportsAtom);
  const pivot = useAtomValue(pivotAtom);
  const pivotReport = vm.reports[pivot];
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
