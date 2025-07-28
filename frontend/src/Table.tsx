import { useAtomValue } from "jotai";
import {
  isSelected,
  pivotAtom,
  type Report,
  type ReportId,
  selectionAtom,
  viewModelAtom,
} from "./atoms.ts";
import clsx from "clsx";
import type { ReactNode } from "react";

export interface ReportTableHead {
  title: string;
}

export function ReportTableHead({ title }: ReportTableHead) {
  const vm = useAtomValue(viewModelAtom);
  const selection = useAtomValue(selectionAtom);
  const pivot = useAtomValue(pivotAtom);

  return (
    <thead>
      <tr>
        <th>{title}</th>
        {vm.reports.map((report, reportId) => {
          if (!isSelected(reportId, selection)) {
            return null;
          }
          const isPivot = reportId === pivot;
          return (
            <td
              key={report.title}
              className={clsx("text-center", isPivot && "text-primary border-primary border-b")}
            >
              {report.title}
            </td>
          );
        })}
      </tr>
    </thead>
  );
}

export interface ReportTableRowProps {
  title: ReactNode;
  cell: (props: { report: Report; reportId: ReportId }) => ReactNode;
  textAlign?: "left" | "right" | "center";
}

export function ReportTableRow({ title, cell, textAlign }: ReportTableRowProps) {
  const vm = useAtomValue(viewModelAtom);
  const selection = useAtomValue(selectionAtom);

  const textAlignClass = {
    left: "text-left",
    right: "text-right",
    center: "text-center",
  }[textAlign ?? "right"];

  return (
    <tr>
      <th>{title}</th>
      {vm.reports.map((report, reportId) => {
        if (!isSelected(reportId, selection)) {
          return null;
        } else {
          return (
            <td key={report.title} className={textAlignClass}>
              {cell({ report, reportId })}
            </td>
          );
        }
      })}
    </tr>
  );
}
