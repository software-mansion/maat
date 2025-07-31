import { useAtomValue } from "jotai";

import { DateTime } from "./DateTime.tsx";
import { Duration } from "./Duration.tsx";
import { RichCell } from "./RichCell.tsx";
import { Section, SectionTable, SectionTitle } from "./Section.tsx";
import { ReportTableHead, ReportTableRow, ReportTableSection } from "./Table.tsx";
import { pivotReportAtom, selectedReportsAtom } from "./atoms.ts";
import { durationTrend } from "./trends.ts";

export function MetricsSection() {
  const selectedReports = useAtomValue(selectedReportsAtom);
  const pivotReport = useAtomValue(pivotReportAtom);

  return (
    <Section id="metrics">
      <SectionTitle>Metrics</SectionTitle>
      <SectionTable>
        <ReportTableHead />
        <ReportTableSection title="Metadata" />
        <tbody>
          <ReportTableRow title="Workspace" cell={(report) => report.metrics.workspace} />
          <ReportTableRow
            title="Scarb Version"
            cell={(report) => <code>{report.metrics.scarbVersion}</code>}
          />
          <ReportTableRow
            title="Foundry Version"
            cell={(report) => <code>{report.metrics.foundryVersion}</code>}
          />
          <ReportTableRow
            title="Ma'at Commit"
            cell={(report) => <code>{report.metrics.maatCommit}</code>}
          />
          <ReportTableRow
            title="Created At"
            cell={(report) => <DateTime value={report.metrics.createdAt} />}
          />
        </tbody>
        <ReportTableSection title="Totals" />
        <tbody>
          <ReportTableRow
            title="Total Execution Time"
            cell={(report) => {
              const trend = durationTrend(
                report.metrics.totalExecutionTime,
                pivotReport?.metrics?.totalExecutionTime ?? null,
                selectedReports.map((r) => r.metrics.totalExecutionTime),
              );
              return (
                <RichCell
                  value={<Duration value={report.metrics.totalExecutionTime} />}
                  trend={trend}
                />
              );
            }}
          />
          <ReportTableRow
            title="Total Projects"
            cell={(report) => `${report.metrics.totalProjects}`}
          />
        </tbody>
      </SectionTable>
    </Section>
  );
}
