import { useAtomValue } from "jotai";
import { applySelection, pivotAtom, selectionAtom, viewModelAtom } from "./atoms.ts";
import { Section, SectionTable, SectionTitle } from "./Section.tsx";
import { ReportTableHead, ReportTableRow } from "./Table.tsx";
import { DateTime } from "./time.tsx";
import { durationTrend, MetricWithTrend } from "./trends.tsx";

export function MetricsSection() {
  const vm = useAtomValue(viewModelAtom);
  const selection = useAtomValue(selectionAtom);
  const pivot = useAtomValue(pivotAtom);

  const selectedReports = applySelection(vm.reports, selection);
  const pivotReport = vm.reports[pivot];

  return (
    <Section defaultOpen>
      <SectionTitle>Metrics</SectionTitle>
      <SectionTable>
        <ReportTableHead title="Parameters" />
        <tbody>
          <ReportTableRow title="Workspace" cell={({ report }) => report.metrics.workspace} />
          <ReportTableRow
            title="Scarb Version"
            cell={({ report }) => <code>{report.metrics.scarbVersion}</code>}
          />
          <ReportTableRow
            title="Foundry Version"
            cell={({ report }) => <code>{report.metrics.foundryVersion}</code>}
          />
          <ReportTableRow
            title="Ma'at Commit"
            cell={({ report }) => <code>{report.metrics.maatCommit}</code>}
          />
          <ReportTableRow
            title="Created At"
            cell={({ report }) => <DateTime value={report.metrics.createdAt} />}
          />
          <ReportTableRow
            title="Total Execution Time"
            cell={({ report }) => {
              const trend = durationTrend(
                report.metrics.totalExecutionTime,
                pivotReport.metrics.totalExecutionTime,
                selectedReports.map((r) => r.metrics.totalExecutionTime),
              );
              return (
                <MetricWithTrend
                  value={report.metrics.totalExecutionTime}
                  trend={trend}
                />
              );
            }}
          />
          <ReportTableRow
            title="Total Projects"
            cell={({ report }) => `${report.metrics.totalProjects}`}
          />
        </tbody>
      </SectionTable>
    </Section>
  );
}
