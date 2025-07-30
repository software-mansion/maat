import { useAtom, useAtomValue } from "jotai";
import { pivotAtom, type Report, selectedReportsAtom, selectionAtom } from "./atoms.ts";
import clsx from "clsx";
import type { ReactNode } from "react";

export interface ReportTableHead {
  title?: string;
}

export function ReportTableHead({ title }: ReportTableHead) {
  const selectedReports = useAtomValue(selectedReportsAtom);
  const [pivot, setPivot] = useAtom(pivotAtom);
  return (
    <thead>
      <tr>
        <th>{title ?? ""}</th>
        {selectedReports.map((report) => {
          const isPivot = report.title === pivot;
          return (
            <td
              key={report.title}
              className={clsx("text-center", isPivot && "text-primary border-primary border-b")}
            >
              <a className="link link-hover" onClick={() => setPivot(report.title)}>
                {report.title}
              </a>
            </td>
          );
        })}
      </tr>
    </thead>
  );
}

export interface ReportTableSectionProps {
  title: string;
}

export function ReportTableSection({ title }: ReportTableSectionProps) {
  const selection = useAtomValue(selectionAtom);
  return (
    <thead>
      <tr>
        <th className="bg-base-200">{title}</th>
        <td colSpan={selection.length} className="bg-base-200" />
      </tr>
    </thead>
  );
}

export interface ReportTableRowProps {
  title: ReactNode;
  cell: (report: Report) => ReactNode;
  textAlign?: "left" | "right" | "center";
}

export function ReportTableRow({ title, cell, textAlign }: ReportTableRowProps) {
  const selectedReports = useAtomValue(selectedReportsAtom);

  const textAlignClass = {
    left: "text-left",
    right: "text-right",
    center: "text-center",
  }[textAlign ?? "right"];

  return (
    <tr>
      <th>{title}</th>
      {selectedReports.map((report) => (
        <td key={report.title} className={textAlignClass}>
          {cell(report)}
        </td>
      ))}
    </tr>
  );
}
