import { useAtomValue } from "jotai";
import {
  type HardwareEnvironment,
  pivotReportAtom,
  selectedReportsAtom,
} from "./atoms.ts";
import { DateTime } from "./DateTime.tsx";
import { Duration } from "./Duration.tsx";
import { Q } from "./Q.tsx";
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

/**
 * Reference specs for CPU models we commonly see, so comparing 2 machines isn't a guessing game.
 * Ordered most-specific first: the generic cloud-Xeon fallback at the end only fires when nothing
 * more specific matched. Add entries here as new machine types show up (e.g. new GCP zones/generations
 * rotate their exact Xeon SKU, and GCP's AMD parts use cloud-only "B"/"9B"-suffixed model numbers that
 * don't appear in retail listings).
 */
const KNOWN_CPU_SPECS: { test: (model: string) => boolean; note: string }[] = [
  // GitHub Actions runners
  {
    test: (m) => m.includes("EPYC 7763"),
    note: "GitHub Actions Linux x64 runner · ~2.45 GHz base, 3.5 GHz boost",
  },
  {
    test: (m) => m.includes("Ampere Altra"),
    note: "GitHub Actions Linux arm64 runner · ~3.0 GHz",
  },
  // Apple Silicon (local dev machines)
  {
    test: (m) => m.includes("Apple M1"),
    note: "Apple Silicon (2020) · up to 3.2 GHz",
  },
  {
    test: (m) => m.includes("Apple M2"),
    note: "Apple Silicon (2022) · up to 3.5 GHz",
  },
  {
    test: (m) => m.includes("Apple M3"),
    note: "Apple Silicon (2023) · up to 4.05 GHz",
  },
  {
    test: (m) => m.includes("Apple M4"),
    note: "Apple Silicon (2024) · up to 4.4 GHz",
  },
  // GCP Compute Engine — cloud-only SKUs, don't match any retail part number
  {
    test: (m) => /EPYC 7B1[23]/.test(m),
    note: "GCP N2D/T2D custom AMD EPYC (Rome/Milan class)",
  },
  {
    test: (m) => /EPYC 9B\d{2}/.test(m),
    note: "GCP C3D custom AMD EPYC (Genoa class)",
  },
  {
    test: (m) => /Xeon\(R\) Platinum 8481C/.test(m),
    note: "GCP C3 custom Intel Xeon (Sapphire Rapids class)",
  },
  {
    test: (m) => /Neoverse-N1/.test(m),
    note: "Arm Neoverse N1 server core (GCP T2A / Ampere Altra class) · ~3.0 GHz",
  },
  // Generic cloud fallback: N1/N2/C2 and most other providers mask the exact SKU in /proc/cpuinfo
  // and only report the clock speed, so this is the best we can say without more specific data.
  {
    test: (m) => /Xeon\(R\) CPU @ [\d.]+\s*GHz/i.test(m),
    note: "Cloud VM Intel Xeon · exact model hidden by hypervisor, clock speed as reported",
  },
];

function cpuSpecNote(cpuModel: string | null): string | null {
  if (cpuModel == null) return null;
  return KNOWN_CPU_SPECS.find((spec) => spec.test(cpuModel))?.note ?? null;
}

/** Short, stable, content-derived label so long hardware descriptions don't blow up the table; full text lives in a legend tooltip. */
function hardwareHash(hardware: HardwareEnvironment): string {
  const str = JSON.stringify(hardware);
  let hash = 0x811c9dc5;
  for (let i = 0; i < str.length; i++) {
    hash ^= str.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193);
  }
  return (hash >>> 0).toString(16).padStart(8, "0").slice(0, 6);
}

function HardwareLegend({
  hardware,
  differsFromPivot,
}: {
  hardware: HardwareEnvironment[];
  differsFromPivot: boolean;
}) {
  return (
    <Q className="tooltip-left" contentClassName="text-left">
      <div className="flex flex-col gap-1.5">
        {hardware.map((h) => (
          <div key={JSON.stringify(h)}>
            <div>
              <code>{hardwareHash(h)}</code> — {formatHardware(h)}
            </div>
            {cpuSpecNote(h.cpuModel) != null && (
              <div className="text-xs opacity-70">
                {cpuSpecNote(h.cpuModel)}
              </div>
            )}
          </div>
        ))}
        {differsFromPivot && <div>Differs from pivot report's hardware</div>}
      </div>
    </Q>
  );
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
              const differsFromPivot =
                pivotReport != null &&
                pivotReport.metrics.hardware.length > 0 &&
                !hardwareListsEqual(hardware, pivotReport.metrics.hardware);
              if (hardware.length > 1) {
                return (
                  <span className="text-warning">
                    Mixed ({hardware.map((h) => hardwareHash(h)).join(", ")}){" "}
                    <HardwareLegend
                      hardware={hardware}
                      differsFromPivot={differsFromPivot}
                    />
                  </span>
                );
              }
              const only = hardware[0];
              if (only == null) {
                return <span className="text-base-content/60">—</span>;
              }
              return (
                <span className={differsFromPivot ? "text-warning" : undefined}>
                  <code>{hardwareHash(only)}</code>{" "}
                  <Q className="tooltip-left" contentClassName="text-left">
                    <div className="flex flex-col gap-1.5">
                      <div>{formatHardware(only)}</div>
                      {cpuSpecNote(only.cpuModel) != null && (
                        <div className="text-xs opacity-70">
                          {cpuSpecNote(only.cpuModel)}
                        </div>
                      )}
                      {differsFromPivot && (
                        <div>Differs from pivot report's hardware</div>
                      )}
                    </div>
                  </Q>
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
