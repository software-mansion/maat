import clsx from "clsx";
import type { ReactNode } from "react";
import type { Hardware, Report } from "./atoms.ts";
import { Section, SectionTable, SectionTitle } from "./Section.tsx";
import { ReportTableHead, ReportTableRow } from "./Table.tsx";

export function HardwareSection() {
  return (
    <Section id="hardware">
      <SectionTitle>Hardware</SectionTitle>
      <SectionTable>
        <ReportTableHead />
        <tbody>
          <HardwareRow title="CPU" value={(hardware) => hardware.cpuModel} />
          <HardwareRow
            title="Cores"
            value={(hardware) => formatCores(hardware)}
          />
          <HardwareRow
            title="Memory"
            value={(hardware) => formatBytes(hardware.memoryBytes)}
          />
          <HardwareRow
            title="Platform"
            value={(hardware) => formatPlatform(hardware)}
          />
          <HardwareMetricRow
            title="CPU steal"
            value={(hardware) => hardware.cpuStealPercent}
            scale={CPU_STEAL_SCALE}
          />
          <HardwareMetricRow
            title="CPU pressure"
            value={(hardware) => hardware.cpuPressurePercent}
            scale={CPU_PRESSURE_SCALE}
          />
        </tbody>
      </SectionTable>
    </Section>
  );
}

interface ContentionScale {
  elevatedAt: number;
  highAt: number;
  description: string;
}

const CPU_STEAL_SCALE: ContentionScale = {
  elevatedAt: 0.5,
  highAt: 2,
  description: "CPU capacity withheld by the hypervisor during the run",
};

const CPU_PRESSURE_SCALE: ContentionScale = {
  elevatedAt: 5,
  highAt: 20,
  description: "Run time with runnable work waiting for CPU",
};

function HardwareMetricRow({
  title,
  value,
  scale,
}: {
  title: ReactNode;
  value: (hardware: Hardware) => number | null;
  scale: ContentionScale;
}) {
  return (
    <ReportTableRow
      title={title}
      textAlign="left"
      cell={(report) => (
        <HardwareMetricValues report={report} value={value} scale={scale} />
      )}
    />
  );
}

function HardwareMetricValues({
  report,
  value,
  scale,
}: {
  report: Report;
  value: (hardware: Hardware) => number | null;
  scale: ContentionScale;
}) {
  const values = [
    ...new Set(
      report.hardware
        .map(value)
        .filter((item): item is number => item !== null),
    ),
  ];
  if (values.length === 0) {
    return <span className="opacity-50">—</span>;
  }
  return (
    <div className="flex flex-col items-start gap-1">
      {values.map((item) => (
        <ContentionBadge key={item} value={item} scale={scale} />
      ))}
    </div>
  );
}

function ContentionBadge({
  value,
  scale,
}: {
  value: number;
  scale: ContentionScale;
}) {
  const severity =
    value >= scale.highAt
      ? {
          label: "high",
          className: "border-error/30 bg-error/10 text-error",
        }
      : value >= scale.elevatedAt
        ? {
            label: "elevated",
            className: "border-warning/30 bg-warning/10 text-warning",
          }
        : {
            label: "low",
            className: "border-success/30 bg-success/10 text-success",
          };

  return (
    <span
      className={clsx(
        "badge gap-1.5 border font-medium tabular-nums",
        severity.className,
      )}
      title={`${scale.description}. Elevated at ${formatPercent(scale.elevatedAt)}, high at ${formatPercent(scale.highAt)}.`}
    >
      <span className="size-1.5 rounded-full bg-current" />
      {formatPercent(value)}
      <span className="opacity-70">{severity.label}</span>
    </span>
  );
}

function HardwareRow({
  title,
  value,
}: {
  title: ReactNode;
  value: (hardware: Hardware) => string | null;
}) {
  return (
    <ReportTableRow
      title={title}
      textAlign="left"
      cell={(report) => <HardwareValues report={report} value={value} />}
    />
  );
}

function HardwareValues({
  report,
  value,
}: {
  report: Report;
  value: (hardware: Hardware) => string | null;
}) {
  const values = [
    ...new Set(report.hardware.map(value).filter((item) => item !== null)),
  ];
  if (values.length === 0) {
    return <span className="opacity-50">—</span>;
  }
  return values.map((item) => <div key={item}>{item}</div>);
}

function formatCores(hardware: Hardware): string | null {
  if (hardware.physicalCores !== null && hardware.logicalCores !== null) {
    return `${hardware.physicalCores} cores / ${hardware.logicalCores} threads`;
  }
  if (hardware.logicalCores !== null) {
    return `${hardware.logicalCores} threads`;
  }
  return null;
}

function formatBytes(bytes: number | null): string | null {
  if (bytes === null) {
    return null;
  }
  const gibibytes = bytes / 1024 ** 3;
  return `${gibibytes.toFixed(gibibytes >= 10 ? 0 : 1)} GiB`;
}

function formatPlatform(hardware: Hardware): string | null {
  const platform = [hardware.architecture, hardware.kernel]
    .filter(Boolean)
    .join(" · ");
  if (!platform) {
    return null;
  }
  return hardware.virtualized ? `${platform} · virtualized` : platform;
}

function formatPercent(value: number | null): string | null {
  if (value === null) {
    return null;
  }
  return `${value.toFixed(value >= 10 ? 0 : value >= 1 ? 1 : 2)}%`;
}
