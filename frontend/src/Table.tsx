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
              className={clsx(isPivot && "text-primary border-primary border-b")}
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
}

export function ReportTableRow({ title, cell }: ReportTableRowProps) {
  const vm = useAtomValue(viewModelAtom);
  const selection = useAtomValue(selectionAtom);

  return (
    <tr>
      <th>{title}</th>
      {vm.reports.map((report, reportId) => {
        if (!isSelected(reportId, selection)) {
          return null;
        } else {
          return <td key={report.title}>{cell({ report, reportId })}</td>;
        }
      })}
    </tr>
  );
}
