import { useAtom, useAtomValue } from "jotai";
import {
  isSelected,
  pivotAtom,
  type ReportId,
  selectedSliceAtom,
  selectionAtom,
  viewModelAtom,
} from "./atoms";
import type { ReactNode } from "react";

export function Slicer() {
  const vm = useAtomValue(viewModelAtom);
  const [selectedSlice, setSelectedSlice] = useAtom(selectedSliceAtom);

  const selection = useAtomValue(selectionAtom);
  const [pivot, setPivot] = useAtom(pivotAtom);

  return (
    <form className="grid grid-cols-[auto_minmax(0,_1fr)] items-baseline gap-3">
      <Fieldset title="Pivot:">
        {vm.reports.map((report, reportId) => {
          if (!isSelected(reportId, selection)) {
            return null;
          }

          return (
            <input
              key={report.title}
              type="radio"
              name="pivot"
              className="btn btn-xs"
              aria-label={report.title}
              checked={pivot === reportId}
              onChange={() => setPivot(reportId)}
            />
          );
        })}
      </Fieldset>

      <Fieldset title="Use a predefined slice:">
        {vm.slices.map((slice, sliceId) => {
          const isActive = "predefined" in selectedSlice && selectedSlice.predefined === sliceId;
          return (
            <input
              key={slice.title}
              type="radio"
              name="predefined-slice"
              className="btn btn-xs"
              aria-label={slice.title}
              checked={isActive}
              onChange={() => setSelectedSlice({ predefined: sliceId })}
            />
          );
        })}
      </Fieldset>

      <Fieldset title="Or compose your own:">
        {vm.reports.map((report, reportId) => {
          const isActive = "custom" in selectedSlice && selectedSlice.custom.includes(reportId);
          return (
            <input
              key={report.title}
              type="checkbox"
              name="custom-slice"
              className="btn btn-xs"
              aria-label={report.title}
              checked={isActive}
              onChange={() => {
                let custom: ReportId[] = [];
                if ("custom" in selectedSlice) {
                  custom = [...selectedSlice.custom];
                }
                if (isActive) {
                  custom = custom.filter((id) => id !== reportId);
                } else {
                  custom.push(reportId);
                }
                custom.sort();
                setSelectedSlice({ custom });
              }}
            />
          );
        })}
      </Fieldset>
    </form>
  );
}

function Fieldset({ title, children }: { title: string; children: ReactNode }) {
  return (
    <fieldset className="contents">
      <legend className="text-sm text-nowrap">{title}</legend>
      <div className="flex flex-wrap gap-1">{children}</div>
    </fieldset>
  );
}
