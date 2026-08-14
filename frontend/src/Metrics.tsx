import { useAtomValue } from "jotai";
import { Fragment } from "react";
import {
  type HardwareEnvironment,
  pivotReportAtom,
  selectedReportsAtom,
} from "./atoms.ts";
import { DateTime } from "./DateTime.tsx";
import { Duration } from "./Duration.tsx";
import { RichCell } from "./RichCell.tsx";
import { Section, SectionTable, SectionTitle } from "./Section.tsx";
import {
  ReportTableHead,
  ReportTableRow,
  ReportTableSection,
} from "./Table.tsx";
import { durationTrend } from "./trends.ts";

function formatHardware(hardware: HardwareEnvironment): string {
  const parts = [
    hardware.cpuModel ?? "unknown CPU",
    hardware.cpuCount != null ? `${hardware.cpuCount} cores` : null,
    hardware.memoryTotalMb != null
      ? `${(hardware.memoryTotalMb / 1024).toFixed(0)} GB RAM`
      : null,
  ].filter((p) => p != null);
  const origin = hardware.ci ? "CI" : "local";
  return `${parts.join(", ")} · ${hardware.os} (${hardware.arch}) · ${origin}`;
}

/** Order-insensitive comparison: merged reports can list the same set of environments in different orders. */
function hardwareListsEqual(
  a: HardwareEnvironment[],
  b: HardwareEnvironment[],
): boolean {
  if (a.length !== b.length) return false;
  const sortedA = a.map((h) => JSON.stringify(h)).sort();
  const sortedB = b.map((h) => JSON.stringify(h)).sort();
  return sortedA.every((s, i) => s === sortedB[i]);
}

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
          <ReportTableRow
            title="Workspace"
            cell={(report) => report.metrics.workspace}
          />
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
          <ReportTableRow
            title="Hardware"
            cell={(report) => {
              const hardware = report.metrics.hardware;
              if (hardware.length === 0) {
                return <span className="text-base-content/60">—</span>;
              }
              if (hardware.length > 1) {
                return (
                  <>
                    <span className="text-warning">
                      Mixed ({hardware.length} environments)
                    </span>
                    <span className="text-base-content/60 text-xs">
                      {hardware.map((h) => (
                        <Fragment key={JSON.stringify(h)}>
                          <br />
                          {formatHardware(h)}
                        </Fragment>
                      ))}
                    </span>
                  </>
                );
              }
              const only = hardware[0];
              if (only == null) {
                return <span className="text-base-content/60">—</span>;
              }
              const differsFromPivot =
                pivotReport != null &&
                pivotReport.metrics.hardware.length > 0 &&
                !hardwareListsEqual(hardware, pivotReport.metrics.hardware);
              return (
                <span
                  className={differsFromPivot ? "text-warning" : undefined}
                  title={
                    differsFromPivot
                      ? "Differs from pivot report's hardware"
                      : undefined
                  }
                >
                  {formatHardware(only)}
                </span>
              );
            }}
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
